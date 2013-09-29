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


import random
import re

from vsa.infra.params import ObjState, ReqState, AlarmType, ILLEGAL_EXT_NAME,\
    EXT_NOT_FOUND, EXT_IS_PRIVATE, EXT_IS_LOCKED, EXT_NOT_RUNNING,\
    EXT_NOT_ENABLED, IsRunning, CACHEVGN
from vsa.events.VSAEvents import SevEnum, Callist
from vsa.infra.infra import tstint, iif
#from san_resources import SanResources


def volstr2obj(val,vtypes='drfbtnhv',pvdin=None,chklock=True,chkstate=True, san=None):
    """
    The description of volstr2obj comes here.
    @param val
    @param vtypes
    @param pvdin
    @param chklock
    @param chkstate
    @param san
    @return
    """
    val = val.strip()
    if len(val) < 2:
        return (ILLEGAL_EXT_NAME,'value is too short or null',None)
    vsp = val.split(':',1)
    if pvdin:
        pvd = pvdin
    else:
        pvd = san.lclprovider
    if len(vsp) > 1 and san.providers.has_key(vsp[0]):
        pvd = san.providers[vsp[0]]
        val = vsp[1]
    if pvdin and pvdin.name != pvd.name:
        return (EXT_NOT_FOUND,'requested provider (%s) is different than needed (%s)' % (pvd.name, pvdin.name),'')
    pfx=val[0]
    lval=val.lower()
    devobj=None
    devtype=''

    if pfx.lower() not in vtypes:
        return (ILLEGAL_EXT_NAME, 'not a valid prefix, disk/volume must start with \
%s followed by the relevant name/numbers, see help class lun' \
% '|'.join([x for x in vtypes]),None)

    if lval=='null':
        return (0,'n',['/null',pvd])
    if lval=='th_null':
        return (0,'t',['/th_null',pvd])

    if lval.startswith('f.'):
        return (0,'f',['/'+val[2:].lstrip('/'),pvd])

    if lval.startswith('b.'):
        blklist=pvd.devdict # TBD add more providers, not just local
        if not blklist.has_key(val[2:]):
            return (EXT_NOT_FOUND,'block name %s not found' % val[2:],None)
        return (0,'b',blklist[val[2:]])

    if lval.startswith('h.'):
        hbtl=val[2:]
        if len(hbtl.split(':')) <> 4:
            return (ILLEGAL_EXT_NAME,'HBTL should contain host:bus:target:lun values','')
        for p in san.disks.values():
            for pt in p.paths.values():
                if pt.hbtl==hbtl and pt.provider.name==pvd.name:
                    devobj=pt
                    break
        if not devobj:
            return (EXT_NOT_FOUND,'HBTL path %s not found' % hbtl,'')
        return (0,'h',devobj)
    if pfx=='d':
        p=''
        m=re.match(r'^d(\d+)-part(\d+)',val)
        if m:
            i=int(m.group(1)); p=m.group(2)
        else:
            i=tstint(val[1:])
            if i < 0:
                return (ILLEGAL_EXT_NAME,'%s is not a valid disk number' % val[1:],None)
        if not san.disks.altdict.has_key(i):
            return (ILLEGAL_EXT_NAME,'disk id %s not found' % val[1:],None)
        devobj=san.disks.altdict[i]
    if pfx=='D':
        p=''
        m=re.match(r'^D(\S+)-part(\d+)',val)
        if m:
            dn=m.group(1); p=m.group(2)
        else:
            dn=val[1:]
        if not san.disks.has_key(dn):
            return (EXT_NOT_FOUND,'disk guid %s not found' % val[1:],None)
        devobj=san.disks[dn]
    if pfx=='D' or pfx=='d':
        if p:
            if not devobj.partitions.has_key(p):
                return (ILLEGAL_EXT_NAME,'Disk %s does not have partition number %s' % (str(devobj),p),'')
            devobj=devobj.partitions[p]
        devtype='d'
    if lval.startswith('v.'):
        devtype='v'
        pv=val[2:].split('.',1)
        if len(pv) < 2:
            return (ILLEGAL_EXT_NAME,'%s is not a valid volume name, type <pool>.<volume>' % val[2:],'')
        if pv[0].endswith(':cachevg'):
            pvd=pv[0].split(':')[0]
            if not san.providers[pvd].cachevg.volumes.has_key(pv[1]):
                return (EXT_NOT_FOUND, '%s cache volume not found' % val[2:], '')
            devobj = san.providers[pvd].cachevg.volumes[pv[1]]
        else:
            if not san.pools.has_key(pv[0]) or not san.pools[pv[0]].volumes.has_key(pv[1]):
                return (EXT_NOT_FOUND,'%s pool or volume name not found , type <pool>.<volume>' % val[2:],'')
            devobj=san.pools[pv[0]].volumes[pv[1]]
    if lval.startswith('r.'):
        if not san.raids.has_key(val[2:]):
            return (EXT_NOT_FOUND,'Raid name %s not found' % val[2:],'')
        devtype='r'
        devobj=san.raids[val[2:]]
    if devobj:
        if devobj.private and san.runmode:
            return (EXT_IS_PRIVATE, '%s is private and cannot be used' % str(devobj), '')
        if chklock and devobj.locked:
            return (EXT_IS_LOCKED,'%s is locked, used by other volumes or has mounted filesystem' % str(devobj),'')
        if chkstate and not IsRunning(devobj):
            return (EXT_NOT_RUNNING, '%s storage object is not in a running state (state=%s)' % (str(devobj),str(devobj.state)),'')
        if devobj.reqstate != ReqState.enabled:
            return (EXT_NOT_ENABLED, '%s requested state is not enabled' % str(devobj),'')
        return (0,devtype,devobj)
    return (ILLEGAL_EXT_NAME,'volume name consist of type (e.g. d|D|v.|r.|..) followed by name/number, see help class lun for more','')


def obj2volstr(obj,txt='',pvd=None):
    """
    The description of obj2volstr comes here.
    @param obj
    @param txt
    @param pvd
    @return
    """
    if pvd:
        pv = pvd.name + ':'
    else:
        pv = ''
    if obj:
        if obj.exttype=='partition':
            return 'D'+obj.parent.guid+'-part'+str(obj.idx)
        if obj.exttype=='physical' :
            return 'D'+obj.guid
        if obj.exttype=='virtual' :
            if obj.pool==CACHEVGN:
                return 'v.'+obj.provider.name+':cachevg.'+obj.lvname
            return 'v.'+obj.pool+'.'+obj.lvname
        if obj.exttype=='raid' :
            return 'r.'+obj.name
        if obj.exttype=='path' :
            return obj.provider.name+':h.'+obj.hbtl
        return pv+'b.'+obj.devfile
    if not txt : return ''
    if txt == '/null' or txt == '/th_null':
        return pv+txt[1:]
    return pv+'f.'+txt[1:]


def ext2path(ext,pvd=None,avgload=50,rnd=True,exclude=[]):
    """
    The description of ext2path comes here.
    @param ext
    @param pvd
    @param avgload
    @param rnd
    @param exclude
    @return
    """
    if ext.exttype=='path' and pvd and not (pvd is ext.provider):
        return (1,'Path Provider (%s) is different than Default (%s)' % (ext.provider.name,pvd.name))
    if ext.exttype != 'physical':
        return (0,ext)
    dsk=ext
    pt=''
    paths=[p for p in dsk.paths() if p.state==ObjState.running and p.reqstate==ReqState.enabled
        and (not pvd or (p.provider is pvd))
        and (not getattr(dsk,'cachepresent',False) or p.cacheon)
        and p.provider not in exclude]
    if len(paths)==0:
        return (1,'Valid paths not found')
    i=random.randint(0,len(paths)-1)
    return (0,paths[i])


cxstr={'0':'SPA0','1':'SPA1','2':'SPA2','3':'SPA3','8':'SPB0','9':'SPB1','A':'SPB2','B':'SPB3'}


def wwn2alias(wwpn,wwnn):
    """
    The description of wwn2alias comes here.
    @param wwpn
    @param wwnn
    @return
    """
    if wwpn[0:6]=='500601':
        tmp='EMC-'+wwnn[8:16]+'-'+cxstr.get(wwpn[7:8].upper(),wwpn[7:8].upper())
    else:
        tmp=wwpn
    return tmp


def BuildSANTree(obj,r):
    """
    The description of BuildSANTree comes here.
    @param obj
    @param r
    @return
    """
    for ch in obj.child_obj:
        co=obj.__dict__[ch]
        if co.get_object_type() == 'VSACollection' or co.get_object_type() == 'RefDict' :
            c=r.AddChild(co.fullpath, co.description, co.icon)
            if co.get_object_type() == 'VSACollection':
                lst=[co[k] for k in sorted(co.keys())]
            else:
                if getattr(co,'table',None): return
                lst=co()
            for v in lst:
                ic=iif(v.icon,v.icon,co.icon)
                c2=c.AddChild(v.fullpath, v.name, ic)
                BuildSANTree(v,c2)
