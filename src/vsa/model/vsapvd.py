# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 Mellanox Technologies, Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import time, os, sys, traceback, socket

from xmlrpclib import ServerProxy, Error
from twisted.internet import defer, threads
from twisted.web.xmlrpc import Proxy
from twisted.internet import error as twisted_error
import xmlrpclib
from IPy import IP
from vsa.infra import infra, logger
from vsa.infra.params import CACHESEP, ObjState, CACHEVGN, RaidLevel, CACHEPFX,\
    IsRunning, Transport, VSAD_XMLRPC_PORT, VSAD_RPC_TIMEOUT, ClusterState
from vsa.client.gui.vsaxmlrpc import VsaQueryFactory
from vsa.model.san import SanPath
from vsa.model.san_partition import SanPartition
from vsa.model.pool import VolGrpSubpool, VolGrpItem
from vsa.model.extent import PoolItem
from vsa.model.fc import FCport
from vsa.model.provider import Provider
from vsa.model.san_vol_group import SanVolgrp
from vsa.model.netif import Netif
from vsa.model import obj2volstr


def cachelv2extstr(lvn):
    """
    The description of cachelv2extstr comes here.
    @param lvn
    @return
    """
    tmp=lvn.replace(CACHESEP,':') # replace cache seperator (signiture) back to ':'
    return (tmp[0],tmp[1:])

#aaa=0
def process_extents(provider, exts, san):
    """
    The description of process_extents comes here.
    @param provider
    @param exts
    @param san
    @return
    """
    if not exts:
        return 0

#   global aaa
#   aaa+=1
#   caller = inspect.getframeinfo(inspect.currentframe().f_back.f_back)[2]
#   logger.eventlog.debug('in process_extents %d: %s' % (aaa, str(caller)))

    based={}
    name2ex={}
    cachedevs={}
    cachetodev={}
    cachedrdevs={}
    cachelvs={}
    pname = provider.name

    for ex in provider.devdict.values():
        ex.updateflag = 0   # allow detecting absent/offline extents
        if ex.exttype == 'physical':
            for part in ex.partitions():
                part.updateflag = 0
            for pt in ex.paths():
                if pt.provider is provider:
                    pt.updateflag = 0
    # allow detecting if cachevg is absent
    provider.cachevg.updateflag = 0

    provider.mdnums=[]
    provider.drbdnums=[]

    for ex in exts:
        try:
            l=None
            lname=ex['devfile']
            name=pname+':'+ex['devfile']
            guid=name

            if ex['extype'] == 'physical' and ex['type'] == 'disk' and ex['state'] != 'absent':
                if 'hbatype' not in ex:
                    ex['hbatype'] = 'scsi'
                guid = ex.get('guid',name)
                # cciss HP array
                if ex['hbatype'] == 'cciss':
                    # '!' is invalid for cache name
                    # and multiple places already do replace from '/' to CACHESEP and back
                    name = pname + ':' + ex['sysfile'].replace('!','_')
                    guid = name
                # address LSI6200 unique is bug (returns same id)
                if ex.get('model','').strip() == 'LSI6200':
                    guid = name
                if not san.disks.has_key(guid):
                    l = san.add_disks(guid,guid,False)
                    l.direct = True
                else:
                    l = san.disks[guid]
                l.serial = ex.get('serial','')
                if l.serial=='Unknown':
                    l.serial=''
                l.vendor = ex.get('vendor','')
                l.model = ex.get('model','')
                l.revision = ex.get('revision','')
##              l.change_state(ObjState.__dict__[ex.get('state','running')])
                if ex['hbatype'] in ['ata', 'cciss', 'fio', 'vgc', 'rssd']:
                    ex['HBTL'] = '99:0:0:0'
                ptkey = pname + ':' + ex['HBTL']
                if not l.paths.has_key(ptkey):
                    path = l.paths.add(ptkey,SanPath(provider,name=ptkey,hbtl=ex['HBTL']))
                else:
                    path = l.paths[ptkey]
                path.updateflag = 1
                path.change_state(ObjState.__dict__[ex.get('state','running')])
                path.devfile=ex['devfile']
                path.sg=ex.get('sg','')
                path.lastseen=time.time()
                path.hbatype = ex['hbatype']
                if path.hbatype in ['fc','iscsi'] :
                    (path.initiator,path.target,path.dstport)=ex['it']

            if ex['extype']=='partition':
                # lname key is devfile and for cciss devices we need to replace '!' to '/'
                if ex['basedon'][0].startswith('cciss'): ex['basedon'][0]=ex['basedon'][0].replace('!','/')
                parent=name2ex[ex['basedon'][0]]
                if parent.partitions.has_key(ex['id']):
                    l = parent.partitions[ex['id']]
                else:
                    l = parent.partitions.add(ex['id'],SanPartition(parent.guid+'-part'+ex['id'],int(ex['id']),0,int(ex['start'])))
                    if not l:
                        logger.eventlog.error('cant add partition: '+parent.guid+'-part'+ex['id'])
                    parent.usedby+=[l]
                    l.provider=provider
                    l.devfile=ex['devfile']
                l.basedon=[parent]
                l.updateflag=1
                l.change_state(parent.state)

            if ex['extype']=='virtual' and ex.has_key('lvuuid'): # TBD add multipath dm
                guid = ex['lvuuid']
                nm=ex['lvname']
                vgn=ex['vgname']
                if vgn.startswith('glb.'):
                    vgn = vgn[4:]
                if vgn == CACHEVGN:
                    vg = provider.cachevg
                elif san.pools.has_key(vgn):
                    vg = san.pools[vgn]
                elif san.pools.has_key(pname+':'+vgn):
                    vg = san.pools[pname+':'+vgn]
                else:
                    logger.eventlog.error('VG %s not found when trying to create LV %s' % (vgn,nm))
                    continue

                if not vg.volumes.has_key(nm):
                    l = vg.add_volumes(nm,guid,provider,False)
                else:
                    l = vg.volumes[nm]
                l.lvname = nm
                l.pool = vgn
                if vgn.startswith('VolGroup00'):
                    l.exposed = False   # hide system volumes
                if nm.startswith('vdisk.') or vgn == CACHEVGN:
                    l.auto = True
                if vgn == CACHEVGN:
                    cachelvs[l.name]=l
                l.change_state(ObjState.__dict__[ex.get('state','running')])

            if ex['extype']=='vg':
                vgn=lname
                glb=False
                if lname.startswith('glb.'):
                    vgn=lname[4:]
                    glb=True
                if vgn.startswith('VolGroup0'):
                    vgn=pname+':'+vgn
                if vgn==CACHEVGN:
                    l=provider.cachevg
                elif not san.pools.has_key(vgn):    # TBD deal with pvd:name
                    l=san.add_pools(vgn,provider)
                else:
                    l=san.pools[vgn]
                    if not glb and l.provider and l.provider.name<>pname:
                        logger.eventlog.error('Duplicate VolGroup Name:  %s, in both [%s,%s] ex=%s,' % (lname,l.provider.name,pname,str(ex)))
                        if not san.pools.has_key(name):
                            l=san.add_pools(name,provider)
                        else:
                            l=san.pools[name]
                if glb:
                    l.glbl=True
                    if l.subpools.has_key(pname):
                        sp=l.subpools[pname]
                    else:
                        sp=l.subpools.add(pname,VolGrpSubpool(pname,provider))
                    sp.attr=ex['attr']
                    sp.change_state(ObjState.running)
                    sp.chunk=int(ex['ext'])/2/1024  # in MB
                    sp.free=sp.chunk*int(ex['free']) # in MB
                    sp.guid=ex['uuid']
                    sp.size=int(ex['size'])/2/1024
                    totsize=0
                    totfree=0
                    for totsp in l.subpools():
                        totsize+=totsp.size
                        totfree+=totsp.free
                    l.size=totsize
                    l.free=totfree
                else:
                    l.attr=ex['attr']
                    l.chunk=int(ex['ext'])/2/1024  # in MB
                    l.free=l.chunk*int(ex['free']) # in MB
                    l.guid=ex['uuid']
                    if vgn==CACHEVGN:
                        provider.cachefree=l.free
                        provider.cachesize=int(ex['size'])/2/1024
                l.change_state(ObjState.running)
                if ex['slaves']:
                    ex['basedon']=[]
                    for sl in ex['slaves']:
                        n=pname+':'+sl['pv'][5:]  # TBD use a persistent value vs devfile
                        if not l.slaves.has_key(n):
                            item=l.slaves.add(n,VolGrpItem(n,provider))
                        else:
                            item=l.slaves[n]
                        item.size=float(sl['psize'])/2/1024
                        item.free=float(sl['pfree'])/2/1024
                        item.attr=sl['attr']
                        item.pe=sl['pe']
                        item.alloc=sl['alloc']
                        item.change_state(ObjState.running)  # TBD set real state
                        ex['basedon']+=[sl['pv'][5:]]

            if ex['extype']=='raid' and not (ex['astate']=='clear'):
                uid=ex.get('uuid',name)
                rname=ex.get('name',uid)
                if not san.raids.has_key(rname):
                    l=san.add_raids(rname,provider)
                else:
                    l=san.raids[rname]
                    if l.provider and l.provider.name != pname:
                        logger.eventlog.error('Duplicate Array Name:  %s, in both [%s,%s] ex=%s,' % (rname,l.provider.name,pname,str(ex)))
                        if not san.raids.has_key(pname+':'+rname):
                            l=san.add_raids(pname+':'+rname,provider)
                        else:
                            l=san.raids[pname+':'+rname]
                if ex['level'].startswith('raid'):
                    ex['level']=ex['level'][4:]
                l.raid = RaidLevel.__dict__[ex['level']]
                if 'degraded' in ex['state']:
                    l.change_state(ObjState.degraded)
                else:
                    l.change_state(ObjState.running)
                l.substate=ex['state']
                l.guid=uid
                if rname.startswith('pool.'):
                    l.auto=True
                if ex.get('rebuild status',''):
                    l.resync=ex['rebuild status'].split('%')[0]
                else:
                    l.resync=''
                if lname[0:2]=='md':
                    if int(lname[2:]) not in provider.mdnums:
                        provider.mdnums+=[int(lname[2:])]
                if ex['slaves']:
                    for sl in ex['slaves']:
                        if not l.slaves.has_key(sl[0]):
                            item=l.slaves.add(sl[0],PoolItem(sl[0],provider))
                        else:
                            item=l.slaves[sl[0]]
                        item.slot=sl[1]
                        item.datastate=sl[2]
                        item.dataerrors=int(sl[3])
                        if sl[2]=='faulty':
                            item.change_state(ObjState.error,'disk is faulty')
                        else:
                            item.change_state(ObjState.running)  # TODO set real state

            if ex['extype']=='dr':
                guid=ex.get('guid',name)
                if not san.raids.has_key(guid):
                    l=san.add_raids(guid,None,False,firstidx=int(ex['minor']))
                    l.raid=RaidLevel.dr
                else:
                    l=san.raids[guid]
                if lname[0:4]=='drbd':
                    if int(lname[4:]) not in provider.drbdnums:
                        provider.drbdnums+=[int(lname[4:])]
                item=None
                peer_down=False
                for slv in l.slaves():
                    if slv.provider and slv.provider is provider:
                        item=slv
                    else:
                        peer_down=(slv.state==ObjState.absent)
                if not item:
                    item=l.add_slaves(None,provider)
                if ex.get('ro','')=='primary':
                    if peer_down:
                        l.change_state(ObjState.degraded)
                    else:
                        l.change_state(ObjState.running)
                    l.provider=provider
                else:
                    ex['state']='offline'
                # TBD - set item in degraded state for DRBD not in data sync
                item.change_state(ObjState.__dict__[ex['state']])
                item.connstate=ex.get('cs','')
                item.datastate=ex.get('ds','')
                item.candidate = (item.datastate == 'uptodate') and \
                        (item.connstate in ['connected','syncsource',
                                'startingsyncs','wfbitmaps',
                                'pausedsyncs','wfconnection'])
                item.role=ex.get('ro','')
                if ex.get('resynced_percent',''):
                    l.resync=ex['resynced_percent']
                else:
                    l.resync=''
                if guid.startswith(CACHEPFX):
                    tmp=guid[len(CACHEPFX)+1:]
                    cachedrdevs[tmp]=l

            if ex['extype']=='cache' and ex['slow']:
                cachedevs[ex['slow']] = ex
                cachetodev[ex['devfile']] = ex['slow']
                cachetodev[ex['dm']] = ex['slow']

            if l:
                l.size=int(ex['size'])/2/1024  # in MB
                if  ex['extype']<>'partition' : l.devfile=ex['devfile']
                l.blkfile=ex.get('dm',l.devfile)
                l.updateflag=1
                if ex.has_key('mount'):
                    l.mount=ex['mount']
                    l.locked=True
                    l.exposed=not (l.mount in ['/','/boot'])
                if ex.has_key('swap'):
                    l.locked=True
                name2ex[lname]=l

            if ex.has_key('basedon'):
                based[lname]=ex['basedon']
        except Exception,err:
            logger.eventlog.error('Process Extent Err: ex=%s, %s' % (str(ex),str(err)))
            traceback.print_exc(file=sys.stdout)
            return 2

    # debug block
    #print "based"
    #print based.keys()
    #print "name2ex"
    #print name2ex.keys()
    #print "cachetodev"
    #print cachetodev.keys()
    #print "cachedevs"
    #print cachedevs.keys()
    # end debug block

    # create extent hirarchy (who is used by who)
    for b in based.keys():
        #print ''
        #print "b:", b
        if name2ex.has_key(b):
            ext = name2ex[b]
            #print "ext:", ext
            for d in based[b]:
                #print "d:", d
                if cachetodev.has_key(d):
                    slvname=cachetodev[d]
                else:
                    slvname=d
                #print "slvname:", slvname
                if name2ex.has_key(slvname):
                    extc = name2ex[slvname]
                    #print "extc:",extc
                    if ext.exttype in ['virtual','pool','raid'] or ext.locked:
                        extc.locked=True
                        if extc.exttype=='partition':
                            extc.parent.locked=True
                        extc.exposed = ext.exposed
                    if ext.exttype=='raid' and ext.raid==RaidLevel.dr:
                        for sl in ext.slaves():
                            if sl.provider is provider:
                                sl.extent = extc
##                  if ext.exttype=='raid' and ext.raid==RaidLevel.dr and ext.slaves.has_key(pname):
##                      ext.slaves[pname].extent=extc
                    if ext.exttype=='raid' and ext.raid<>RaidLevel.dr and ext.slaves.has_key(d):
                        ext.slaves[d].extent=extc
                    if ext.exttype=='pool' and ext.slaves.has_key(pname+':'+d):
                        ext.slaves[pname+':'+d].extent=extc
                    if extc not in ext.basedon:
                        ext.basedon+=[extc]
                    if ext not in extc.usedby:
                        extc.usedby+=[ext]

    # set cachedrdev
    # TODO: works for physical disks only
    #   ??? need to do it for raids/pools/etc or find other solution
    for lv,dr in cachedrdevs.items():
        vol=san.disks.get(lv)
        if vol:
            vol.cachedrdev=dr

    # update lvs for dr raids if missing
    for nm,vol in cachelvs.items():
        dr=san.raids.get(CACHEPFX+nm)
        if dr and dr.devices and len(dr.devices) < 2 and vol not in dr.devices:
            # devices has 1 vol and its not this one
            dr.devices+=[vol]

    # detect/mark devices with cache
    for devname,devex in cachedevs.items():
        if name2ex.has_key(devname):
            ext = name2ex[devname]
            for k,val in devex.items():
                ext.cachedict[k] = val
            ext.cachepresent = True
            pdict = {}
            if ext.exttype == 'physical':
                ext.cachedrdev = san.raids.get(ext.cachedict['cname'])
                if ext.cachedrdev:
                    ext.cachedrdev.auto = True
                    ext.cachedrdev.private = True
                for pt in ext.paths():
                    if pt.provider is provider:
                        pdict[pt.devfile] = pt
                if pdict.has_key(devname):
                    pdict[devname].cacheon = True
                    pdict[devname].cachedev = ext.cachedict['devfile']
                    pdict[devname].cachedict = ext.cachedict
            volname = devex['cname'][len(CACHEPFX):]
            if provider.cachevg.volumes.has_key(volname):
                ext.cachesize = provider.cachevg.volumes[volname].size

    # maintain a list of providers which have a cache LV, per physical disk extent
    for ext in name2ex.values():
        if ext.exttype=='physical' and pname in ext.cachepvds:
            # remove this provider from the disk cache provider list
            # (clean so we can verify the list doesnt contain old entries)
            ext.cachepvds.remove(pname)
    for lvn in provider.cachevg.volumes.keys():
        (extype,exstr)=cachelv2extstr(lvn)
        if extype=='D' and san.disks.has_key(exstr):
            # add the current provider to the list if we found a cache LV
            san.disks[exstr].cachepvds+=[pname]

    # mark absent devices (not discovered in this pass)
    for ex in provider.devdict.values():
        if ex.exttype == 'physical':
            for part in ex.partitions():
                if part.updateflag == 0 and IsRunning(part):
                    if part.usedinluns:
                        part.change_state(ObjState.absent,'partition not found on load')
                    else:
                        ex.partitions.delete(part)
            for pt in ex.paths():
                if pt.provider is provider and pt.updateflag == 0 and IsRunning(pt):
                    pt.change_state(ObjState.absent,'path not found on load')
        elif ex.exttype != 'partition' and ex.updateflag == 0 and IsRunning(ex):
            ex.change_state(ObjState.absent,'extent not found on load')

    #print "cachevg state: %s" % str(provider.cachevg.state)
    if provider.cachevg.state == ObjState.absent:
        provider._reset_cachevg()

    provider.devdict = name2ex
    return 0

def process_target(san,provider,pid,st,init=False):
    """
    The description of process_target comes here.
    @param san
    @param provider
    @param pid
    @param st
    @param init
    @return
    """
    tgid2tg={}
    redirs=[]
    pname=provider.name

    for tg in san.targets():
        if tg.device is provider:
            tg.updateflag = 0   # allows to detect absent targets

    for t in st['targets'] :
        redir=t.get('redir','')
        if redir:
            redirs+=[int(t['tid'])]
            if san.lclprovider and (provider is san.lclprovider):
                # make sure the redirect is on the master
                if san.targets.has_key(t['name']):
                    tg=san.targets[t['name']]
                else:
                    tg=san.add_targets(t['name'],None)
                tg.redirect=True
                tg.redir_tid=int(t['tid'])
                if tg.id<>tg.redir_tid :
                    logger.eventlog.info('rdir tid %s not eq tid %s on target %s' % (tg.redir_tid,tg.id,t['name']))
                tg.updateflag=1
            else:
                print 'detected redir target %s on provider %s (which is not a master)' % (t['tid'],pname)
                (e,res) = provider.vsaagnt_rpc('del_target', pid, int(t['tid']), 1)
                logger.eventlog.info('deleted redir target %s on %s' % (t['tid'],pname))
            continue
        if san.targets.has_key(t['name']):
            tg=san.targets[t['name']]
            tg.acls=[]
            tg.initiators={}
            tg.users=[]
            if tg.redirect and not tg.device:
                tg.device=provider
            for l in tg.luns.values():
                l.updateflag=0
        else:
            tg=san.add_targets(t['name'],provider)
            if 'iqn.vsa.vdisk.' in t['name'] or 'iqn.vsa.vhba.' in t['name']:
                tg.auto=True
        tg.id=int(t['tid'])
        tg.pid=pid
        if t['state']=='ready':
            tg.change_state(ObjState.running)
        else:
            tg.change_state(ObjState.offline)
        tg.transport=Transport.__dict__[t['driver']]
        tg.updateflag=1
        tgid2tg[tg.id]=tg

    for a in st['acls']:
        if a[0] not in redirs :
            tgid2tg[a[0]].acls+=[a[1]]
            # Auto learn/create server objects when finding ACLs w/o servers
            if init :
                if tgid2tg[a[0]].server and a[1]<>'ALL':
                    ips = [str(i) for i in tgid2tg[a[0]].server.ips]
                    if a[1] not in ips : tgid2tg[a[0]].server.ips+=[a[1]]
                if a[1] and not tgid2tg[a[0]].server :
                    if a[1]=='ALL':
                        tgid2tg[a[0]].server=san.servers['everyone']
                        san.servers['everyone'].targets[tgid2tg[a[0]].name]=tgid2tg[a[0]]
# TBD fix me
##              else :
##                  found=0
##                  for s in san.servers.values():
##                      ips = [str(i) for i in s.ips]
##                      if a[1] in ips :
##                          tgid2tg[a[0]].server=s
##                          s.targets[tgid2tg[a[0]].name]=tgid2tg[a[0]]
##                          found=1
##                          break
##                  if not found :
##                      s=san.add_servers()
##                      s.ips=[IP(a[1])]
##                      tgid2tg[a[0]].server=s
##                      s.targets[tgid2tg[a[0]].name]=tgid2tg[a[0]]

    for c in st['connections']:
        if c[0] not in redirs:
            tgid2tg[c[0]].initiators[c[1]]=c[2:]

    pdict={}
    for dev in provider.devdict.values():
        if dev.exttype=='physical':
            for pt in dev.paths.values():
                if pt.provider is provider:
                    pdict[pt.devfile]=pt

    for l in st['luns']:
        lid=l['lid']
        if int(l['tid']) not in redirs:
            tgt=tgid2tg[int(l['tid'])]
            if tgt.luns.has_key(lid):
                lun=tgt.luns[lid]
            else:
                lun=tgt.add_luns(lid)
            lun.stype=l['type']
            d=l['bspath']
            lun.devfile=d
            if not lun.volume and d.startswith('/dev/') :
                # TODO , fix devices that were added as hbtl wont use path
                if pdict.has_key(d[5:]) and 'iqn.vsa.vhba.' in tgt.name:
                    lun.volume=pdict[d[5:]]
                    lun.path=pdict[d[5:]]
                elif provider.devdict.has_key(d[5:]):
                    lun.volume=provider.devdict[d[5:]]
            if d=='/tmp_null':
                lun.devstr='/null'
            elif d=='/tmp_th_null':
                lun.devstr='/th_null'
            if lun.volume and lun not in lun.volume.usedinluns:
                lun.volume.usedinluns+=[lun]
            # with the next we set pools/??? created in initiator side as private
            if lun.volume and lun.volume.usedby:
                for ext in lun.volume.usedby:
                    ext.private=True
            lun.bstype=l['bstype']
            lun.scsisn=l['scsisn']
            lun.scsiid=l['scsiid']
            if l['on']=='yes':
                lun.change_state(ObjState.running)
            else:
                lun.change_state(ObjState.offline)
            lun.online=l['on']
            lun.updateflag=1
            lun.size=int(l['size'])

    update_targets_state(san,provider,pid)

    return tgid2tg.values()

def update_targets_state(san,provider,pid,absent=False):
    """
    The description of update_targets_state comes here.
    @param san
    @param provider
    @param pid
    @param absent
    @return
    """
    for tg in san.targets():
        if tg.device is provider and tg.pid==pid and tg.state==ObjState.running:
            if tg.updateflag==0 or absent:
                tg.change_state(ObjState.absent,'Target not discovered')
                for lun in tg.luns():
                    lun.state = ObjState.created
            elif not absent:
                # check if lun path is absent
                for lun in tg.luns():
                    if lun.id <> 0 and lun.state == ObjState.running and \
                    lun.path and lun.path.state == ObjState.absent:
                        lun.state = ObjState.absent

def process_fc(san,provider,hbas,tgts):
    """
    The description of process_fc comes here.
    @param san
    @param provider
    @param hbas
    @param tgts
    @return
    """
##  (e,hbas,tgts)=vsag.read_fc()
    provider.fcports.clr()  #={}
    for hba in hbas.values():
        wwpn=('%16.16X' % int(hba['port_name'],16)).upper()
        if not san.fcports.has_key(wwpn):
            fcp=FCport(wwpn)
            san.fcports.add(wwpn,fcp)
        else:
            fcp=san.fcports[wwpn]
            # TBD check/log if wwpn moved to differnt node
        fcp.wwnn=('%16.16X' % int(hba['node_name'],16)).upper()
        fcp.fabric=hba['fabric_name']
        fcp.speed=hba['speed']
        if fcp.speed == 'unknown':
            fcp.change_state(ObjState.down)
        elif hba['port_state'].lower() == 'online':
            fcp.change_state(ObjState.running)
        else:
            fcp.change_state(hba['port_state'])
        fcp.roles='i'
        fcp.system=provider
        fcp.port_type=hba['port_type']
        fcp.scsihost=hba['host']
        fcp.maxnpiv=int(hba.get('maxnpiv','0'))
        fcp.npivinuse=int(hba.get('npivinuse','0'))
        fcp.vports=hba.get('vports',[])
        fcp.targets={}
        provider.fcports[hba['host']]=fcp
    for (k,v) in provider.fcports.items() :
        for vp in v.vports :
            provider.fcports['host'+vp].parport=k
    for hbt,tg in tgts.items() :
        wwpn=(tg['port_name'][2:]).upper()
        if not san.fcports.has_key(wwpn) :
            fcp=FCport(wwpn)
            san.fcports.add(wwpn,fcp)
            fcp.wwnn=(tg['node_name'][2:]).upper()
        else :
            fcp=san.fcports[wwpn]
            # TBD check/log if wwpn moved to differnt node
        if fcp.roles<>'i' :
            h=tg['host']
            ifcp=provider.fcports[h]
            fcp.fabric=ifcp.fabric
            if tg['port_state'].lower()=='online' : fcp.change_state(ObjState.running)
            else : fcp.change_state(tg['port_state'])
            fcp.roles='t'
            provider.fcports[h].targets[tg['HBT']]=fcp

def get_vgn(vg):
    """
    The description of get_vgn comes here.
    @param vg
    @return
    """
    vgn = vg.name
    if vg.glbl:
        vgn = 'glb.' + vgn
    return vgn

def get_devpath(extent):
    """
    The description of get_devpath comes here.
    @param extent
    @return
    """
    if extent.exttype == 'path':
        if extent.cacheon:
            return '/dev/' + extent.cachedev
##      ex=extent.parent
##  else : ex = extent
    if getattr(extent,'cachepresent',False):
        dev = extent.cachedict['devfile']
    else:
        dev = getattr(extent,'devfile','')

    return '/dev/'+dev


class LoopbackException(Exception):
    pass


class ProviderInitializeException(Exception):
    pass


class VsaProvider(Provider):
    def __init__(self,name='', url='', usr='root', pwd='123456', role=None, san=None, local=False):
        """
        The description of __init__ comes here.
        @param name
        @param url
        @param usr
        @param pwd
        @param role
        @param san
        @param local
        @return
        """
        if not url:
            url = socket.gethostname()
        self.name = url.split(':')[0]
        self.info = {}
        if ':' not in url:
            url += ':%s' % str(VSAD_XMLRPC_PORT)

        # Set current ip and initialize empty list of active ips for rpc retries
        curip = socket.gethostbyname(url.split(':')[0])
        logger.eventlog.debug('provider url: %s (ip: %s)' % (url, curip))
        # don't use loopback
        if curip == '127.0.0.1':
            raise LoopbackException("Can't use loopback interface")
        self.curr_ip = IP(curip)
        self.active_ips = [self.curr_ip,]
        print 'active ips:',self.active_ips

        # From now on change default socket timeout
        # TODO: more accurate is to change timeout specifically for proxy factories
        socket.setdefaulttimeout(VSAD_RPC_TIMEOUT)

        # Inilialize sync and async RPC proxies
        self.update_proxies(self.curr_ip)

        Provider.__init__(self,self.name,url,usr,pwd)

        # set role before getting info
        if role:
            (e,res) = self.set_role(role)
            if e:
                raise Exception(res)

        if self.get_info():
            logger.eventlog.error('Failed to initialize provider %s' % name)
            if local:
                raise ProviderInitializeException()
            else:
                self.state = ObjState.absent
        else:
            self.name = self.info['name']

        self.mdnums = []
        self.drbdnums = []

        self._reset_cachevg()

        self.__last_extents_processing = 0
        self._load_count = 0
        self.loading = False
##      self.name=name
##      if not san.providers.has_key(self.name) : self.load(False)

    def _reset_cachevg(self):
        """
        The description of _reset_cachevg comes here.
        @return
        """
        if self.cachevg:
            self.cachevg.delete()
        self.cachevg = SanVolgrp(CACHEVGN, self)
        self.cachevg.auto = True
        self.cachevg.fullpath = '%s:cachevg' % self.name
        self.cachefree = 0
        self.cachesize = 0

    def hnderr(self, err, err_msg = 'RPC Communication Error') :
        """
        The description of hnderr comes here.
        @param err
        @param err_msg
        @return
        """
        logger.eventlog.error('%s: pvd=%s, %s' % (err_msg, self.name,str(err)))
        self.error=True
        self.errstr=err
        if self.url : self.change_state(ObjState.absent, err_msg)

    def create_ordered_ips(self):
        """
        Create ordered list of active ips.
        Starting from current ip, i.e. last good ip, ending on the previous one
        @return: None
        """
        # Get current ip index in the list of active ips
        try:
            curr_ip_idx = self.active_ips.index(self.curr_ip)
            # Creating ordered list of active ips starting from current ip and ending on the previous one
            self.ordered_ips = self.active_ips[curr_ip_idx:] + self.active_ips[0:curr_ip_idx]
        except Exception, err:
            logger.eventlog.error('Failed to find current IP index: pvd=%s, exception: %s'
                        % (self.name, str(err)))
            # Use active ips list as is
            self.ordered_ips = self.active_ips
            if self.ordered_ips:
                ip=self.ordered_ips[0]
                self.curr_ip = ip
                self.update_proxies(ip)

    def update_proxies(self, ip):
        """
        Update both sync and async proxies with ip
        @param ip: ip for proxy URL
        @return: None
        """
        self.vsaagnt = ServerProxy('http://' + str(ip) + ':' + str(VSAD_XMLRPC_PORT))
        self.vsaagnt_async = Proxy('http://' + str(ip) + ':' + str(VSAD_XMLRPC_PORT))
        self.vsaagnt_async.queryFactory = VsaQueryFactory

    def vsaagnt_rpc(self, rpc, *args):
        """
        Generic method for RPC calls to VSA agent.
        Implements RPC call, switches provider interface on failure.
        First RPC is tried on last good ip aka curr_ip that is always updated on successful RPC.
        @param rpc: rpc method name
        @param args: arguments
        @return: tuple of error code and result, error = 0 on success
        """
        logger.eventlog.debug('pvd: %s rpc: %s%s' % (self.name, rpc, repr(args)))
##      print 'pvd: %s rpc: %s%s' % (self.name, rpc, repr(args))

        # Create ordered list of active ips
        self.create_ordered_ips()

        # init err msg
        err = 'rpc error: no ip in self.ordered_ips'

        #TODO an argument if to retry or not when rpc fails. use it for monitor for example

        # Try RPC on all active IPs
        for ip in self.ordered_ips:
            # Update proxies with ip
            self.update_proxies(ip)

            try:
                # Perform RPC converting string method name to callable method
                result = getattr(self.vsaagnt, rpc)(*args)

                # Update current ip by the one RPC succeeded with and return
                self.curr_ip = ip
                return (0, result)
            except (xmlrpclib.ProtocolError, socket.error, socket.gaierror, socket.timeout), err:
                logger.eventlog.error('Sync RPC Communication Error: pvd: %s rpc: %s ip %s failure %s. Retrying alternate interface'
                            % (self.name, rpc, ip, str(err)))
            except Exception, err:
                logger.eventlog.error('Sync RPC General Error: pvd: %s rpc: %s ip: %s failure: %s traceback: %s'
                            % (self.name, rpc, ip, str(err), traceback.format_exc()))
                self.change_state(ObjState.error, 'Agent error on call %s, %s' % (rpc,str(err)))
                return(3, 'Agent error on call %s, %s' % (rpc,str(err)))

        # If we are here, there was communication error on all interfaces
        self.hnderr(err, 'Sync RPC Communication Error')
        return(2, 'Connection Error')

    def saferpc(self,fn):
        """
        The description of saferpc comes here.
        @param fn
        @return
        """
        def rpcf(*args, **kwargs):
            """
            The description of rpcf comes here.
            @param *args
            @param **kwargs
            @return
            """
            try:
                return fn(*args, **kwargs)
            except Exception,err:
                logger.eventlog.error('RPC Error '+str(err))
                self.error=True
                return None
        return rpcf

    def change_states_on_error(self):
        """
        Change related objects states on error
        @return
        """
        for ex in self.devdict.values():
            if (ex.exttype=='raid' and ex.raid==RaidLevel.dr) :
                for sl in ex.slaves() :
                    if sl.provider is self : sl.change_state(ObjState.absent,'no access to provider',silent=True)
                ex.change_state(ObjState.degraded,'no access to one provider')
            elif ex.exttype=='physical' :
                for pt in ex.paths() :
                    if pt.provider is self : pt.change_state(ObjState.absent,'no access to provider',silent=True)
            else :
                ex.change_state(ObjState.absent,'no access to provider',silent=True)
        for tg in self.parent.targets():
            if tg.device is self and tg.state==ObjState.running:
                tg.change_state(ObjState.absent,'no access to provider',silent=True)
                for lun in tg.luns() : lun.state=ObjState.created

    def process_extents(self, exts, utime):
        """
        The description of process_extents comes here.
        @param exts
        @param utime
        @return
        """
        t = self.__last_extents_processing
        #logger.eventlog.debug('process_extents: old: %s , new: %s' % (str(t),str(utime)))
        if utime < t:
            logger.eventlog.debug('skipping extents processing of old result')
            return 0
        process_extents(self, exts, self.parent)
        self.__last_extents_processing = utime

    def load_sync(self, info=True):
        """
        Synchronous load
        @param info: if to request provider info
        @return: None
        """
        logger.eventlog.debug('Start sync load: pvd %s' % self.name)

        # Get provider info
        if info:
            self.get_info()

        # Get and process extents
        utime = time.time()
        (e,res) = self.vsaagnt_rpc('get_extents')
        if e:
            self.change_states_on_error()
            return (e,res)
        (e,exts) = res
        if e:
            return (e,exts)
        self.process_extents(exts, utime)
        self.change_state(ObjState.running)

        # Get and process targets
        for p in range(self.info['tgts']):
            self.load_targets(p, init = True, getopt = True)

        # Get and process fc
        (e,hbas,tgts)=self.vsaagnt.read_fc()
        (e, res)=self.vsaagnt_rpc('read_fc')
        if e: return (e, res)
        (e,hbas,tgts) = res
        process_fc(self.parent,self,hbas,tgts)

        # Get and process ifs
        (e, res)=self.vsaagnt_rpc('get_ifs')
        if e: return (e, res)
        (e, gifs) = res
        self.process_ifs(gifs)
        self.after_refresh()

        return (0,'')

    def load(self, info=True, sync=False):
        """
        Load full VSA data from SAN to model.
        If sync, call synchronous load method. Otherwise, perform async load.
                Generates a chain of asynchronous RPC calls to provider handled in callbacks
        that generate the next RPC call in turn.
                Loads extents, targets, FC and interfaces and stores in the model.

        Each RPC call adds specific callback got_*_cb() and the mutual errback got_error_eb()
        They represent a re-write of the appropriate synchronous get_*() methods with the following rules:
        - result is passed as a tuple of original RPC result and is broken apart into appropriate variables
        - original method arguments are passed in callRemote() and follow the result argument in got_*_cb() method

        _load_count attribute is used for load status indication.
        It's incremented on each rpc call and decremented on each callback/errback.
        Zero value indicates the load is finished.

        @param info: if to get provider info
        @return: None
        """
        if sync:
            self.load_sync(info)
            return

        #logger.eventlog.debug('Start async load: pvd %s' % self.name)

        # If load requested for the same provide while another load is not finished, return.
        if self._load_count:
            return

        # Create ordered list of active ips and iterator for retries
        self.create_ordered_ips()
        if not self.ordered_ips:
            logger.eventlog.error("Could not get an ip for provider %s" % self.name)
            return
        self.ip_iter = iter(self.ordered_ips)

        self.loading = True

        # Update proxies with the first IP in ordered list
        self.update_proxies(self.ip_iter.next())

        # Initialize rpc and callback depending on info
        if info:
            rpc = 'get_pvdinfo'
            cb = self.got_info_cb
        else:
            rpc = 'get_extents'
            cb = self.got_extents_cb

        # Call rpc, add callback and errback with arguments for possible retrial
        d = self.vsaagnt_async.callRemote(rpc)
        self._load_count += 1
        if info:
            d.addCallback(cb)
        else:
            d.addCallback(cb, time.time())
        d.addErrback(self.got_error_eb, rpc, cb)
        d.addCallback(self.check_load_end)
        d.addErrback(self.check_load_end)

    def got_error_eb(self, failure, rpc, cb, *args):
        """
        Failed RPC errback
        Original rpc method, callback and arguments are passed to the errback for retrials.
        @param failure: failure exception
        @param rpc: remote procedure name
        @param cb: callback assigned to original rpc
        @param args: arguments of the original rpc
        @return: None
        """
        self._load_count -= 1;

        logger.eventlog.debug('Errback: pvd: %s rpc: %s%s' % (self.name, rpc, repr(args)))

        exc_msg = failure.getErrorMessage()

        # If the exception is not communication-related, interrupt the load.
        if not failure.check(twisted_error.TimeoutError, twisted_error.ConnectError,
                twisted_error.ConnectionRefusedError, twisted_error.NoRouteError,
                twisted_error.ServiceNameUnknownError):
            logger.eventlog.error('Async RPC General Error. Interrupting the load: pvd: %s rpc: %s failure: %s'
                        % (self.name, rpc, exc_msg))
            self.change_state(ObjState.error, 'Agent error on async call %s, %s' % (rpc, exc_msg))
            return failure

        # The exception is connection-refused, probably no vsad access, interrupt the load.
        if failure.check(twisted_error.ConnectionRefusedError):
            logger.eventlog.error('Async RPC Connection refused Error on provider %s - Agent is not responding'
                        % self.name)
            self.change_state(ObjState.absent, 'Agent refused connection on call %s, %s' % (rpc, exc_msg))
            self.change_states_on_error()
            return failure


        # The exception is communication-related
        logger.eventlog.error('Async RPC Communication Error: pvd: %s rpc: %s failure: %s'
                    % (self.name, rpc, exc_msg))

        # Get next interface IP for retrial
        try:
            ip = self.ip_iter.next()
        except StopIteration:
            # All interfaces retried with failure. Interrupt the load.
            logger.eventlog.error('Async RPC failed on all interfaces. Interrupting the load: pvd: %s rpc: %s'
                        % (self.name, rpc))
            self.change_state(ObjState.absent, 'Agent communication error on call %s, %s' % (rpc, exc_msg))
            self.change_states_on_error()
            return failure

        logger.eventlog.error('Async RPC - Retrying alternate interface: pvd: %s rpc: %s ip: %s' % (self.name, rpc, str(ip)))

        # Update current IP. If rpc succeeds, it will stay as a last good IP for future rpcs.
        self.curr_ip = ip

        # Update proxies with the new ip
        self.update_proxies(ip)

        # Retry the original rpc, add original callback with arguments
        # and errback with original callback and its arguments for possible future retrials
        d = self.vsaagnt_async.callRemote(rpc, *args)
        self._load_count += 1
        d.addCallback(cb, *args)
        d.addErrback(self.got_error_eb, rpc, cb, *args)
        d.addCallback(self.check_load_end)
        d.addErrback(self.check_load_end)

        return failure

    def got_info_cb(self, result):
        """
        Got info callback
        @param result: provider info
        @return: None
        """
        self._load_count -= 1

        # Process got info result
        self.info = result
        self._update_info()

        # Issue next rpc
        rpc = 'get_extents'
        d = self.vsaagnt_async.callRemote(rpc)
        self._load_count += 1
        d.addCallback(self.got_extents_cb, time.time())
        d.addErrback(self.got_error_eb, rpc, self.got_extents_cb)
        d.addCallback(self.check_load_end)
        d.addErrback(self.check_load_end)

    def got_extents_cb(self, result, utime):
        """
        Got extents callback
        @param result: result tuple of error code and extents
        @return: None
        """
        self._load_count -= 1
        (e, exts) = result
        if e:
            print str(exts)
            logger.eventlog.error('Error in get_extents call, '+str(exts))
        else:
            self.process_extents(exts, utime)
            self.change_state(ObjState.running)

        rpc = 'get_tgtshow'
        for pid in range(self.info['tgts']) :
            d = self.vsaagnt_async.callRemote(rpc, pid)
            self._load_count += 1
            d.addCallback(self.got_tgtshow_cb, pid)
            d.addErrback(self.got_error_eb, rpc, self.got_tgtshow_cb, pid)
            d.addCallback(self.check_load_end)
            d.addErrback(self.check_load_end)

        rpc = 'read_fc'
        d = self.vsaagnt_async.callRemote(rpc)
        self._load_count += 1
        d.addCallback(self.got_fc_cb)
        d.addErrback(self.got_error_eb, rpc, self.got_fc_cb)
        d.addCallback(self.check_load_end)
        d.addErrback(self.check_load_end)

    def got_tgtshow_cb(self, result, pid):
        """
        Got tgt callback
        @param result: result tuple of error code and storage target
        @param pid: tgt pid
        @return: None
        """
        self._load_count -= 1
        (e, st) = result
        if not e:
            tgts=process_target(self.parent,self,pid,st,True)
            rpc = 'get_tgopt'
            for t in tgts:
                if not t.iscsioptrd:
                    d = self.vsaagnt_async.callRemote(rpc, t.pid, t.id)
                    self._load_count += 1
                    d.addCallback(self.got_tgopt_cb, t)
                    d.addErrback(self.got_error_eb, rpc, self.got_tgopt_cb, t)
                    d.addCallback(self.check_load_end)
                    d.addErrback(self.check_load_end)
        else:
            update_targets_state(self.parent,self,pid,absent=True)

    def got_tgopt_cb(self, result, target):
        """
        Got tgopt callback
        @param result: result tuple of error code and result
        @param target: target object
        @return: None
        """
        self._load_count -= 1
        (e, res) = result
        if e : return(e,res)
        target.iscsioptrd = res[1]

    def got_fc_cb(self, result):
        """
        Got fc callback
        @param result: result tuple of error code, hbas and tgts
        @return: None
        """
        self._load_count -= 1
        (e, hbas, tgts) = result
        process_fc(self.parent,self,hbas,tgts)

        rpc = 'get_ifs'
        d = self.vsaagnt_async.callRemote(rpc)
        self._load_count += 1
        d.addCallback(self.got_ifs_cb)
        d.addErrback(self.got_error_eb, rpc, self.got_ifs_cb)
        d.addCallback(self.check_load_end)
        d.addErrback(self.check_load_end)

    def got_ifs_cb(self, result):
        """
        Got ifs callback
        @param result: result tuple of error code and ifs
        @return: None
        """
        self._load_count -= 1
        (e, gifs) = result
        self.process_ifs(gifs)
        self.after_refresh()

    def after_refresh(self,err=False):
        """
        The description of after_refresh comes here.
        @param err
        @return
        """
        for tg in self.parent.targets():
            if tg.state == ObjState.absent and tg.device and (tg.device is self):
                print 're-create/update target on absent : ',tg.name
                tg.update()
            elif tg.state == ObjState.created:
                print 'try to re-create/update target: %s' % tg.name
                tg.update()

    def check_load_end(self, result):
        """
        Added as callback or errback to async rpc deferred.
        Check if load is finished.
        If yes, call parent (SAN resource) refresh finish callback.
        @param result: for cb - previous cb result; for eb - failure
        @return: None
        """
        #logger.eventlog.debug('check_load_end: pvd %s load_count %d' % (self.name, self._load_count))
        if not self._load_count:
            self.loading = False
            self.parent.load_finished(self.name)

    def get_ifs(self):
        """
        The description of get_ifs comes here.
        @return
        """
        try:
            (e,gifs)=self.vsaagnt.get_ifs()
        except (xmlrpclib.ProtocolError, socket.error, socket.gaierror),err:
            self.hnderr(err)
            return(2,'Connection Error')
        self.process_ifs(gifs)

    def process_ifs(self, gifs):
        """
        Process interfaces
        @param gifs
        @return
        """
        tmpifcs=[]
        for nic in gifs :
            tmpifcs+=[nic[0]]
            if self.ifs.has_key(nic[0]):
                ifc=self.ifs[nic[0]]
                ifc.mac=nic[2]
                ifc.ip=IP(nic[3])
                ifc.bcast=nic[4]
                ifc.mask=IP(nic[5])
                ifc.dhcp=nic[6]=='dhcp'
##              if nic[3]=="0.0.0.0" : ifc.change_state(ObjState.degraded)
##              else : ifc.change_state(ObjState.__dict__[nic[8]])
            else :
                ifc=self.ifs.add(nic[0],Netif(nic[0],link=nic[1],mac=nic[2],ip=nic[3],bcast=nic[4],mask=nic[5],dhcp=nic[6]=='dhcp'))
##              if nic[3]=="0.0.0.0" : ifc.state=ObjState.degraded
##              else : ifc.state=ObjState.__dict__[nic[8]]
            state=nic[8]
            if nic[3]=="0.0.0.0" and state!='slaved' : ifc.change_state(ObjState.degraded,'no IP')
            else : ifc.change_state(ObjState.__dict__[state])
            ifc.parif=nic[7]
            ifc.speed=int(nic[9])
            if ':' in nic[0] : ifc.isvirtual=True
            else : ifc.isvirtual=False

        self.active_ips = []
        for k,i in self.ifs.items():
            if k not in tmpifcs:
                i.change_state(ObjState.down)
            else:
                # Add ip of running and managed interface to the active ip list
                if i.state == ObjState.running and i.mng and not i.isvirtual:
                    self.active_ips.append(i.ip)

    def docmd(self,argv, ignoreOutput=False):
        """
        The description of docmd comes here.
        @param argv
        @param ignoreOutput
        @return
        """
        (e,res) = self.vsaagnt_rpc('process_call', argv, ignoreOutput)
        if e: return (e, res)
        return res

    def reboot(self,force):
        """
        The description of reboot comes here.
        @param force
        @return
        """
        cmd=['reboot']
        if force : cmd+=['-f']
        return self.docmd(cmd)

    def set_date(self,datestr):
        """
        The description of set_date comes here.
        @param datestr
        @return
        """
        return self.docmd(['date','-s','%s' % datestr])

    def get_date(self) :
        """
        The description of get_date comes here.
        @return
        """
        (e,txt)=self.docmd(['date'])
        if not e and txt : txt=txt.splitlines()[0]
        return (e,txt)

    def get_info(self):
        """
        The description of get_info comes here.
        @return
        """
        (e,res) = self.vsaagnt_rpc('get_pvdinfo')
        if e:
            return e
        self.info = res
        self._update_info()
        return e

    def _update_info(self):
        """
        The description of _update_info comes here.
        @return
        """
        self.fullname = self.info['fullname']
        self.version = self.info['version']
        self.tgtprocs = self.info['tgts']
        self.clusterstate = ClusterState.__dict__[self.info['cluster']]

    def set_role(self, role):
        """
        The description of set_role comes here.
        @param role
        @return
        """
        if role in infra.VSA_ROLES:
            e,o = self.vsaagnt_rpc('set_role', role)
            if not e:
                self.role = role
            return e,o
        return (1, 'invalid role')

    def get_log(self,name='tgt'):
        """
        The description of get_log comes here.
        @param name
        @return
        """
        (e,res)=self.vsaagnt_rpc('get_log', name)
        if e: return ['Connection Error']
        return res

    def set_if(self,ifname,dhcp=False,ip='',mask='',bcast='',vlan='',mtu=0):
        """
        The description of set_if comes here.
        @param ifname
        @param dhcp
        @param ip
        @param mask
        @param bcast
        @param vlan
        @param mtu
        @return
        """
        (e,res) = self.vsaagnt_rpc('set_if', ifname, dhcp, ip, mask, bcast, vlan, mtu)
        if e: return (e, res)
        return res

    def get_stt(self):
        """
        The description of get_stt comes here.
        @return
        """
        (e,res) = self.vsaagnt_rpc('get_stt')
        if e: return (e, res)
        return res

    def get_ibstt(self):
        """
        The description of get_ibstt comes here.
        @return
        """
        (e,res) = self.vsaagnt_rpc('get_ibstt')
        if e: return (e, res)
        return res

    def get_ifstt(self):
        """
        The description of get_ifstt comes here.
        @return
        """
        (e,res) = self.vsaagnt_rpc('get_ifstt')
        if e: return (e, res)
        return res

    def load_extents(self):
        """
        The description of load_extents comes here.
        @return
        """
        count = getattr(self,'aaa',0)
        count += 1
        self.aaa = count
        utime = time.time()
        (e,res) = self.vsaagnt_rpc('get_extents')
        if e: return (e,res)
        (e,exts) = res
        if e: return (e,exts)
        self.process_extents(exts, utime)
        return (0,'')

    def load_targets(self,pid=0,init=False,getopt=False):
        """
        The description of load_targets comes here.
        @param pid
        @param init
        @param getopt
        @return
        """
        gettid = getopt or self.san_interface is None or not self.san_interface.runmode
        (e,res) = self.vsaagnt_rpc('get_tgtshow', pid, gettid)
        if e: return (e,res)
        (e,st) = res
        if e: return (e,st)
        if not isinstance(st,dict):
            print 'pvd load targets - st: %s' % st
            return (1,st)
        tgts = process_target(self.parent,self,pid,st,init)
        if getopt:
            for t in tgts:
                (e,res2) = self.vsaagnt_rpc('get_tgopt', t.pid, t.id)
                if not e:
                    t.iscsioptrd=res2[1]
        return res

    def add_target(self,trgobj,name,server=None,params={},redir='',refresh=True):
        """
        The description of add_target comes here.
        @param trgobj
        @param name
        @param server
        @param params
        @param redir
        @param refresh
        @return
        """
        acl=[]
        if server: acl=[str(ip) for ip in server.ips]
        if trgobj.id>0 : tid=trgobj.id
##      if redir : tid=trgobj.id
        else : tid=infra.getnextspace([t.id for t in self.parent.targets.values()])
        (e,res) = self.vsaagnt_rpc('create_target', trgobj.pid, name, tid, str(trgobj.transport), acl, params, redir)
        if e: return (e, res)
        if refresh:
            e,r = self.load_targets(trgobj.pid)
            if e: return e,r
        (e,res2) = self.vsaagnt_rpc('get_tgopt', trgobj.pid, trgobj.id)
        if not e : trgobj.iscsioptrd=res2[1]
        return res

    def del_target(self,trgobj,force=False,doload=True):
        """
        The description of del_target comes here.
        @param trgobj
        @param force
        @param doload
        @return
        """
        (e,res) = self.vsaagnt_rpc('del_target', trgobj.pid, trgobj.id, force)
        if e:
            return (e, res)
        if doload:
            self.load_targets(trgobj.pid)
        return res

    def update_target(self,trgobj,server=None,params={},refresh=True):
        """
        The description of update_target comes here.
        @param trgobj
        @param server
        @param params
        @param refresh
        @return
        """
        acl=[]
        if server: acl=[str(ip) for ip in server.ips]
        (e,res) = self.vsaagnt_rpc('update_target', trgobj.pid, trgobj.id, acl, params)
        if e: return (e, res)
        if refresh: self.load_targets(trgobj.pid)
        return res

    def add_lun(self,trgobj,lid,path='',bstype='rdwr',params={},refresh=True):
        """
        The description of add_lun comes here.
        @param trgobj
        @param lid
        @param path
        @param bstype
        @param params
        @param refresh
        @return
        """
        # TBD map volume to bspath
        if isinstance(path,str):
            bspath = path
            if path == '/null':
                bspath = '/tmp_null'
                bstype = 'null'
            elif path == '/th_null':
                bspath = '/tmp_th_null'
                bstype = 'th_null'
        else:
            bspath = get_devpath(path)
        (e, res)=self.vsaagnt_rpc('add_lun', trgobj.pid, trgobj.id, lid, bspath, bstype, params)
        if e:
            return (e, res)
        if refresh:
            self.load_targets(trgobj.pid)
        return res

    def del_lun(self,trgobj,lid,force=0):
        """
        The description of del_lun comes here.
        @param trgobj
        @param lid
        @param force
        @return
        """
        (e, res)=self.vsaagnt_rpc('del_lun', trgobj.pid, trgobj.id, lid, force)
        if e: return (e, res)
        self.load_targets(trgobj.pid)
        return res

    def update_lun(self,trgobj,lid,path='',bstype='rdwr',params={},refresh=True):
        """
        The description of update_lun comes here.
        @param trgobj
        @param lid
        @param path
        @param bstype
        @param params
        @param refresh
        @return
        """
        (e, res)=self.vsaagnt_rpc('update_lunparam', trgobj.pid, trgobj.id, lid, params)
        if e: return (e, res)
        if refresh: self.load_targets(trgobj.pid)
        return res

    def get_tgopt(self,trgobj):
        """
        The description of get_tgopt comes here.
        @param trgobj
        @return
        """
        (e, res)=self.vsaagnt_rpc('get_tgopt', trgobj.pid, trgobj.id)
        if e: return (e, res)
        return res

    def set_tgopt(self,trgobj,opt):
        """
        The description of set_tgopt comes here.
        @param trgobj
        @param opt
        @return
        """
        (e, res)=self.vsaagnt_rpc('set_tgopt', trgobj.pid, trgobj.id, opt)
        if e: return (e, res)
        (e,res2) = self.vsaagnt_rpc('get_tgopt', trgobj.pid, trgobj.id)
        if not e : trgobj.iscsioptrd=res2[1]
        return res

    def get_tgstats(self,tglist):
        """
        The description of get_tgstats comes here.
        @param tglist
        @return
        """
        tgs=[]; rt=0
        tgs=[[t.pid,t.id] for t in tglist]
        (e, res)=self.vsaagnt_rpc('get_tgstats', tgs)
        if e: return (e, res)

        (e, rt, res) = res
        if e: return (e, res)
        tgdict={}; lines=[]
        for t in tglist : tgdict[t.pid,t.id]=t.name
        for l in res :
            lines+=[[tgdict[l[0],int(l[1])]]+l[2:]]
        return (e,rt,lines)

    def load_fc(self):
        """
        The description of load_fc comes here.
        @return
        """
        (e, res)=self.vsaagnt_rpc('read_fc')
        if e: return (e, res)
        (e,hbas,tgts) = res
        process_fc(self.parent,self,hbas,tgts)

    def add_vport(self,host,wwnn,wwpn):
        """
        The description of add_vport comes here.
        @param host
        @param wwnn
        @param wwpn
        @return
        """
        (e, res)=self.vsaagnt_rpc('add_vport', host, wwnn, wwpn)
        if e: return (e, res)
        self.load_fc()
##      time.sleep(1) # TBD make async
##      self.load_extents()
        return res

    def del_vport(self,host,wwnn,wwpn):
        """
        The description of del_vport comes here.
        @param host
        @param wwnn
        @param wwpn
        @return
        """
        (e, res)=self.vsaagnt_rpc('del_vport', host, wwnn, wwpn)
        if e: return (e, res)
        self.load_fc()
        return res

    def rescan(self,host):
        """
        The description of rescan comes here.
        @param host
        @return
        """
        line='rescan-scsi-bus.sh %s' % host
        (e,txt)=self.docmd(line.strip().split(), True)
        return (e,txt)

    def add_raid(self, md, slaves, force=False, loadonly=False):
        """
        The description of add_raid comes here.
        @param md
        @param slaves
        @param force
        @param loadonly
        @return
        """
        drives = [get_devpath(s) for s in slaves]
        num = infra.getnextspace(self.mdnums)
        options = {
            'chunk': md.chunk,
            'spare': md.spare,
            'parity': md.parity,
            'write-mostly': md.writemostly,
            'write-behind': md.behind
            }
        (e, res) = self.vsaagnt_rpc('add_md', \
                'md%d' % num, md.name, str(md.raid), drives, \
                options, force, loadonly)
        if e:
            return (e, res)
        self.load_extents()
        return res

    def del_raid(self,md):
        """
        The description of del_raid comes here.
        @param md
        @return
        """
        drives = [get_devpath(s.extent) for s in md.slaves() if s.extent]  # TBD make sure cache device doesnt change/remove
        zero = True
        (e, res) = self.vsaagnt_rpc('del_md', md.devfile, md.name, drives, zero)
        if e:
            return (e, res)
        return res

    def replace_raid_device(self,md,slave,vol):
        """
        The description of replace_raid_device comes here.
        @param md
        @param slave
        @param vol
        @return
        """
        (e,res) = self.vsaagnt_rpc('del_mddev', md.devfile, [get_devpath(slave.extent)])
        if e:
            return (e,res)
        e,r = res
        if e:
            return res
        (e,res) = self.vsaagnt_rpc('add_mddev', md.devfile, [get_devpath(vol)])
        if e:
            return (e,res)
        return res

    def add_cachedevs(self,slaves,force=False):
        """
        The description of add_cachedevs comes here.
        @param slaves
        @param force
        @return
        """
        vg=self.cachevg
        if vg.state==ObjState.created:
            return self.add_vg(vg,slaves,force)
        else : return (0,'cachedevs already configured (%s)' % str(vg.state))

    def add_vg(self,vg,slaves,force=False):
        """
        The description of add_vg comes here.
        @param vg
        @param slaves
        @param force
        @return
        """
##      for s in slaves :
##          if not force and s.exttype=='path' and len(s.parent.partitions)>0 :
##              return (1,'cant use devices with partitions to create a pool')
        drives=[get_devpath(s) for s in slaves]
        (e, res)=self.vsaagnt_rpc('add_vg', get_vgn(vg), drives, force)
        if e: return (e, res)
        self.load_extents()
        return res

    def del_vg(self,vg):
        """
        The description of del_vg comes here.
        @param vg
        @return
        """
        drives=[get_devpath(s.extent) for s in vg.slaves() if s.extent]
        (e, res)=self.vsaagnt_rpc('del_vg', get_vgn(vg), drives)
        if e: return (e, res)
        self.load_extents()
        return res

    def add_volume(self,vol):
        """
        The description of add_volume comes here.
        @param vol
        @return
        """
        options = {
            'readahead': vol.readahead,
            'stripes': vol.stripes,
            'stripesize': vol.stripesize
            }
        (e, res) = self.vsaagnt_rpc('add_volume', vol.lvname, get_vgn(vol.parent), str(vol.size)+'M', options)
        if e:
            return (e, res)
        self.load_extents()
        return res

    def extend_volume(self,vol,size):
        """
        The description of extend_volume comes here.
        @param vol
        @param size
        @return
        """
        volpath = '/dev/'+vol.devfile
        (e, res)=self.vsaagnt_rpc('extend_volume', volpath, str(size)+'M')
        if e: return (e, res)
        self.load_extents()
        return res

    def reduce_volume(self,vol,size):
        """
        The description of reduce_volume comes here.
        @param vol
        @param size
        @return
        """
        volpath = '/dev/'+vol.devfile
        (e, res)=self.vsaagnt_rpc('reduce_volume', volpath, str(size)+'M')
        if e: return (e, res)
        self.load_extents()
        return res

    def del_volume(self, vol):
        """
        The description of del_volume comes here.
        @param vol
        @return
        """
        (e, res) = self.vsaagnt_rpc('del_volume', get_vgn(vol.parent), vol.lvname)
        if e:
            return (e, res)
        self.load_extents()
        return res

    def config_drbd(self,name,idx,lip,rip,ldev,rdev,primary=True,protocol='C',loadonly=False):
        """
        The description of config_drbd comes here.
        @param name
        @param idx
        @param lip
        @param rip
        @param ldev
        @param rdev
        @param primary
        @param protocol
        @param loadonly
        @return
        """
        rpvd=rdev.provider
        print 'dev: %s, %s path: %s, %s' % (str(ldev),str(rdev),get_devpath(ldev),get_devpath(rdev))
        (e, res)=self.vsaagnt_rpc('config_drbd', primary,name,'/dev/drbd'+str(idx),self.fullname,str(lip),
            str(4261+idx), get_devpath(ldev),rpvd.fullname,str(rip),str(4261+idx),get_devpath(rdev),protocol,loadonly)
        if e: return (e, res)
        self.load_extents()
        return res

    def remove_drbd(self,res):
        """
        The description of remove_drbd comes here.
        @param res
        @return
        """
        (e, r)=self.vsaagnt_rpc('remove_drbd', res)
        if e: return (e, r)
        self.load_extents()
        return r

    def promote_drbd(self,res):
        """
        The description of promote_drbd comes here.
        @param res
        @return
        """
        # promote drbd with 3 attemps
        for i in range(3):
            (e,r) = self.update_drbd(res,'primary')
            if e == 0:
                break
            time.sleep(1)
        return (e,r)

    def update_drbd(self,res,opr=''):
        """
        The description of update_drbd comes here.
        @param res
        @param opr
        @return
        """
        (e, r)=self.vsaagnt_rpc('update_drbd', res, opr)
        if e:
            logger.eventlog.warning('update_drbd %s err: %d %s' % (self.name,e,r))
            return (e, r)
        self.load_extents()
        return r

    def add_lv_for_cache(self,extent,cachesize):
        """
        0 - success, created
        1 - success, exists
        2 - error @param extent
        @param cachesize
        return
        """
        cvolname = obj2volstr(extent)
        cvolname = cvolname.replace(':',CACHESEP) # replace ':' with a legal volume char
        if self.cachevg.volumes.has_key(cvolname):
            logger.eventlog.debug('found already created lv for cache %s' % cvolname)
            vol = self.cachevg.volumes[cvolname]
            return (1,vol)
        else:
            e,r = self.cachevg.find_space(cachesize)
            if e:
                return (2, 'failed to create lv for cache, %s' % r)
            vol = self.cachevg.add_volumes(cvolname,size=cachesize,auto=True)
            if vol:
                (e,r) = vol.update()
                if e:
                    self.cachevg.volumes.delete(vol,force=True)
                    return (2,'failed to create/update cache volume %s ,' % cvolname + r)
            else:
                logger.eventlog.debug('new cache volume %s is null' % cvolname)
                return (2,'new cache volume %s is null' % cvolname)
        return (0,vol)

    def add_cache(self,ext,cachesize=10,force=False):
        """
        The description of add_cache comes here.
        @param ext
        @param cachesize
        @param force
        @return
        """
        if ext.exttype == 'path':
            extent=ext.parent
        else:
            extent=ext
        if extent.cachepresent:
            return (0,'Cache already present')
        cvolname = obj2volstr(extent)
        cvolname = cvolname.replace(':',CACHESEP) # replace ':' with a legal volume char
        (lve,vol) = self.add_lv_for_cache(extent,cachesize)
        if lve > 1:
            return (lve,vol)
        loadonly = bool(lve)
        return self.create_cache(ext,vol,cvolname,loadonly,force)

    def create_cache(self, ext, vol, cvolname, loadonly=False, force=False):
        """
        The description of create_cache comes here.
        @param ext
        @param vol
        @param cvolname
        @param loadonly
        @param force
        @return
        """
        if not loadonly:
            print 'create cache: %s fast: %s  slow: %s' % (CACHEPFX+cvolname, '/dev/'+vol.devfile, '/dev/'+ext.devfile)
            (e, res) = self.vsaagnt_rpc('add_cache', CACHEPFX+cvolname, '/dev/'+vol.devfile, '/dev/'+ext.devfile)
        else:
            print 'loading cache: %s fast: %s  slow: %s' % (CACHEPFX+cvolname, '/dev/'+vol.devfile, '/dev/'+ext.devfile)
            (e, res) = self.vsaagnt_rpc('load_cache', '/dev/'+vol.devfile, force)
        if e:
            return (e,res)
        self.load_extents()
        return res

    def del_cache(self, extent, destroy=False, force=True):
        """
        The description of del_cache comes here.
        @param extent
        @param destroy
        @param force
        @return
        """
        if not extent.cachepresent or not extent.cachedict:
            return (1,'Cache not present')
        if extent.exttype == 'physical':
            cdict = None
            for pt in extent.paths():
                if (pt.provider is self) and pt.cacheon:
                    cdict = pt.cachedict
                    cachept = pt
                    break
            if not cdict:
                return (1,'no paths with cache on this provider (%s)' % self.name)
        else:
            cdict = extent.cachedict
        cachename = cdict['cname']
        lvname = cdict['ssd']
        if destroy:
            destroydev = '/dev/' + cdict['ssd']
        else:
            destroydev = ''
        # delete the flash cache device
        (e, o) = self.vsaagnt_rpc('del_cache', cachename, destroydev, force)
        if e:
            return (e, o)
        extent.cachepresent = False
        extent.cachedict = {}
        if extent.exttype == 'physical':
            cachept.cacheon = False
            cachept.cachedev = ''
            cachept.cachedict = {}
        # delete drbd first if exists, before deleting the lv (locked)
        if extent.exttype == 'physical' and extent.cachedrdev:
            return o
        return self.del_cache_lv(cdict)

    def del_cache_lv(self, cdict):
        """
        The description of del_cache_lv comes here.
        @param cdict
        @return
        """
        cachename = cdict['cname']
        lvname = cdict['ssd']
        # delete the cache logical volume
        vol = cachename[len(CACHEPFX):]
        print 'del cachevol: ',vol
        logger.eventlog.debug('del cache vol: %s lvname: %s' % (vol, lvname))
        if self.cachevg.volumes.has_key(vol):
            (e,o) = self.cachevg.volumes.delete(self.cachevg.volumes[vol], force=True)
            if e:
                return (e,o)
        return (0, 'cache lv removed')

    def get_cache_stt(self,name):
        """
        The description of get_cache_stt comes here.
        @param name
        @return
        """
        (e, res)=self.vsaagnt_rpc('get_cache_stt', name)
        if e: return (e, res)
        logger.eventlog.debug(str(res))
        return res

    def act_cache(self,action):
        """
        The description of act_cache comes here.
        @param action
        @return
        """
        (e, res)=self.vsaagnt_rpc('act_cache', action)
        if e: return (e, res)
        return res

    def set_dev_params(self,extent,params):
        """
        The description of set_dev_params comes here.
        @param extent
        @param params
        @return
        """
        (e, res) = self.vsaagnt_rpc('set_dev_params', extent.devfile, params)
        if e:
            return (e, res)
        return res
