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


from vsa.model import volstr2obj, ext2path, obj2volstr
from vsa.model.san_base import  SanBase
from vsa.infra.params import RaidLevel, ObjState, IsRunning
from vsa.infra import logger
from twisted.internet import reactor
import random
from vsa.model.extent import Extent, PoolItem
from vsa.model.vsa_collections import VSACollection
from vsa.infra.infra import printsz, getnextspace
#===============================================================================
# from sanp_lun import Sanplun
#===============================================================================


class SanRaidGrp(Extent):
    child_obj=['slaves','inluns']
    # TODO can loadonly be replaced with other method?
    set_params=['reqstate','raid','chunk','parity','devices','behind','readahead','vparams','cachesize',
        'loadonly','spare','writemostly']
    newonly_fields=['raid','chunk','parity','provider','spare','writemostly','behind','loadonly']
    #show_columns=[' ','Idx','Name','Raid','Slaves','Size','Cache','Resync','Provider']
    #ui_buttons=[add_btn,del_btn,mapto_btn,addtotgt_btn,addtopool_btn,addisk_btn,extmon_btn]

    def __init__(self,name='',provider=None,raid=RaidLevel.none,devs=[],auto=False):
        """
        The description of __init__ comes here.
        @param name
        @param provider
        @param raid
        @param devs
        @param auto
        @return
        """
        Extent.__init__(self,'',name,'Storage RAID')
        self.exttype='raid'
        self.provider=provider
        self.raid=raid   # '0' '1' '5' '6' '10' 'multipath' 'dr'
        self.slaves=VSACollection(PoolItem,self,'slaves',desc='Raid Members/Slaves',icon='hard_disk.png')
        self.chunk=0
        self.free=0
        self.spare=0
        self.parity=''
        self.behind=-1    # value 0 is for default mdadm value
        self.writemostly=False
        self.resync=''
        self.devices=devs
        self.devsign=''
        self.mdnum=0
        self.manual=False
        self.auto=auto
        self.loadonly=False
        self._flush()

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.locked*'L',self.idx,self.name,self.raid,len(self.slaves),printsz(self.size),printsz(self.cachesize),self.resync,getattr(self.provider,'name','')]

    def after_state_change(self,old,new,errstr='',params={},silent=False):
        """
        The description of after_state_change comes here.
        @param old
        @param new
        @param errstr
        @param params
        @param silent
        @return
        """
        if new==ObjState.running or new==ObjState.degraded:
            self.loadonly=True

    def get_dr_candidates(self,exclude=None):
        """
        The description of get_dr_candidates comes here.
        @param exclude
        @return
        """
        if self.raid != RaidLevel.dr:
            return None
        candidates = [s for s in self.slaves() if s.candidate and \
                s.provider.state != ObjState.absent and \
                s.provider is not exclude]
        return candidates

    def promote_one(self,checkluns=True,exclude=None):
        """
        The description of promote_one comes here.
        @param checkluns
        @param exclude
        @return
        """
        if self.raid != RaidLevel.dr:
            return
        # TBDXX handle promote for replicated cache devices
        if checkluns and len(self.usedinluns):
            return
        sls = self.get_dr_candidates(exclude)
        if not sls:
            logger.eventlog.debug("drbd current provider: %s" % str(self.provider))
            logger.eventlog.debug("drbd exclude: %s" % str(exclude))
            logger.eventlog.error('cant promote any slave on raid/dr group %s' % self.name)
            self.change_state(ObjState.error,'can not promote any slave')
            return (1,'can not promote any slave')
        prims=[p for p in sls if p.state==ObjState.running]
        if len(prims)==1 : return (0,'')
        if len(sls)==1 : slave=sls[0]
        else : slave=sls[random.randint(0,1)]
        return slave.promote(checkluns=checkluns)

    def solve_split_brain(self):
        """
        The description of solve_split_brain comes here.
        @return
        """
        if self.state != ObjState.running or self.raid != RaidLevel.dr or len(self.slaves) <> 2:
            return
        primary=None
        secondary=None
        standalone=False
        wfconnection=True
        for slave in self.slaves():
            # one of the slaves should be in standalone state
            # the other one can be standalone or wfconnection
            if slave.connstate not in ['standalone', 'wfconnection']:
                standalone=False
                break
            if slave.connstate == 'standalone':
                standalone=True
                wfconnection=False
            if slave.role == 'primary':
                primary=slave
            else:
                secondary=slave
        # check if both nodes are in wfconnection state
        if wfconnection:
            # need to wait for get_extents to refresh the states
            reactor.callLater(2.0,self.solve_split_brain)
            return
        if not standalone:
            return
        if not primary or not secondary:
            logger.eventlog.debug('DR split brain detected on %s but cannot solve it' % self.name)
            # XXX both primary or both secondary
            return
        logger.eventlog.info('DR split brain detected on %s. trying to solve it' % self.name)
        (e,r) = secondary.provider.update_drbd(self.name, 'discard-my-data')
        (e,r) = primary.provider.update_drbd(self.name, 'connect')

    def replace_device(self, poolitem, volstr):
        """
        The description of replace_device comes here.
        @param poolitem
        @param volstr
        @return
        """
        if self.raid == RaidLevel.dr:
            return (1,'DR raids are not supported')
        if poolitem not in self.slaves():
            return (1, 'Cant detect slave device')
        (e,t,vol) = volstr2obj(volstr, san=self.san_interface)
        if e:
            return (e,t)
        # TODO  check new extent size is at least the size of old
        #       check old is faulty?
        return self.provider.replace_raid_device(self,poolitem,vol)

    def add_slaves(self,idx,provider=None):
        """
        The description of add_slaves comes here.
        @param idx
        @param provider
        @return
        """
        if idx == None:
           idx = str(getnextspace(self.slaves.keys(),0))
        if idx in self.slaves.keys():
           return None
        tmpslv = PoolItem(idx,provider)
        return self.slaves.add(idx,tmpslv)

    def set_provider(self,san,key,val='',test=0):
        """
        The description of set_provider comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        devlist=san.providers.keys()
        if self.provider and self.provider.name==val : return (0,'')
        if val not in devlist : return (1,'provider name %s does not exist, please specify a valid name' %val)
        if test : return (0,'')
        self.provider=san.providers[val]
        return (0,'')

    def get_provider(self,san,key):
        """
        The description of get_provider comes here.
        @param san
        @param key
        @return
        """
        if self.provider : return (0,self.provider.name)
        return (0,'')

    def set_devices(self,san,key,val='',test=0):
        """
        The description of set_devices comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        devobjs=[]
        sign=''
        first=True
        tmppvd=None
        if len(val) > 2 and val[0] in ['+','-']:
            sign=val[0]
            val=val[1:]
        dl=val.split(';')
        for d in dl:
            (e,t,v)=volstr2obj(d,'dvhb',self.provider,chklock=False,chkstate=san.runmode, san=self.san_interface)
            if e:
                return (e,t)
            usedbyme=False
            for ext in v.usedby:
                if ext is self:
                    usedbyme=True
            if v.locked and not usedbyme:
                return (1,'Device %s is locked and cannot be used to form a Raid' % v.name)
            devobjs+=[v]
        if not test:
            self.devices=devobjs
            self.devsign=sign
        return (0,'')

    def get_devices(self,san,key):
        """
        The description of get_devices comes here.
        @param san
        @param key
        @return
        """
##        if not self.manual : return (0,'')
        tmp=[]
        for d in self.slaves():
            if d.extent:
                tmp+=[obj2volstr(d.extent)]
        return (0,';'.join(tmp))

    def __used(self):
        """
        The description of __used comes here.
        @return
        """
        tot=0
        for l in self.basedon : tot+=l.used
        return tot/1024

    totused=property(__used)

    def _removeSlaves(self):
        """
        helper method for delete()
        """
        for s in self.slaves() :
            self.slaves.delete(s)

    def delete(self,force=False):
        """
        The description of delete comes here.
        @param force
        @return
        """
        if self.state==ObjState.created:
            self._removeSlaves()
            return (0,'')
        if self.auto and not force:
            return (1,'Cannot Delete Auto Generated Raids')
        (e,o) = 0, ''
        if self.usedinluns:
            return (1,'cannot remove raid. used in target %s' % self.usedinluns[0].parent.name)
        if self.usedby:
            return (1,'cannot remove raid. used by %s %s' % (self.usedby[0].description, self.usedby[0].name ))
        if self.cachesize>0:
            return (1,'cannot remove raid, remove cache first')
        if self.raid==RaidLevel.dr:
            self.state=ObjState.delete
            for s in self.slaves():
                if s.provider:
                    (e,o)=s.provider.remove_drbd(self.name)
                    if e and not force:
                        return (e,o)
            (e,o) = (0,'')
        else:
            self.state=ObjState.delete
            (e,o)=self.provider.del_raid(self)
        if not e:
            self._removeSlaves()
        self.loadonly=False
        return (e,o)

    def _update_md_raid(self,flags='',pvd=None):
        """
        The description of _update_md_raid comes here.
        @param flags
        @param pvd
        @return
        """
        if pvd and self.provider and pvd != self.provider:
            return (0,'')
        if self.state == ObjState.absent and not self.devices:
            # create device list from slave objects, in recovery state
            self.devices = [d.extent for d in self.slaves() if d.extent]
        if self.devices and (self.state==ObjState.created or self.state==ObjState.absent):
            if str(self.raid) not in ['0','1','10','5','6','linear']:
                return (1,'Only RAID 0/1/10/5/6/linear creation is supported at this time')
            if str(self.raid) == '6' and len(self.devices) < 4:
                return (1,'must have at least 4 devices for level 6')
            if len(self.devices) < 2:
                return (1,'must have at least 2 devices (specified by the devices property) to form an array')
            if self.spare > 0 and str(self.raid) in ['0','linear']:
                return (1,'spare setting is incompatible with raid %s' % self.raid)
            if len(self.devices) - self.spare <= 1:
                return (1,'invalid number of raid devices')
            if (self.writemostly and str(self.raid) != '1'):
                return (1,'write-mostly is valid for RAID1 only')
            tmppvd = None
            first = True
            devlist = []
            for device in self.devices:
                if device.exttype == 'physical' and len(device.paths) > 1:
                    return (1, 'cant use devices with multiple paths')
                (e,pt) = ext2path(device, self.provider)
                if e:
                    return (e, 'cant add Raid slave %s, ' % str(device))
                if pvd and not (pvd is pt.provider):
                    # this raid is not related to the provider we are updating (pvd<>None)
                    return (0, 'not me')
                if first:
                    if self.provider and not (pt.provider is self.provider):
                        return (1, 'devices must belong to the same provider specified for this raid  (%s)' % self.provider.name)
                    tmppvd = pt.provider
                    first = False
                elif not pt.provider is tmppvd:
                    return (1, 'all devices must belong to the same provider (%s)' % tmppvd.name)
                devlist += [pt]
            if not self.provider:
                self.provider = tmppvd
            tmp = [d.name for d in devlist]
            print 'create raid %s name: %s on %s devs: %s' % (self.raid,self.name,self.provider.name,','.join(tmp))
            (e,r)=self.provider.add_raid(self,devlist,force=False,loadonly=self.loadonly)
            print e,r
            if e:
                return (e,r)
            if self.cachesize > 0:
                # make sure to update cache
                # XXX could use the flags arg
                self._updatedattr.append('cachesize')
            self.devices=[]
        return (0,'')

    def _update_raid_cachesize(self):
        """
        The description of _update_raid_cachesize comes here.
        @return
        """
        _load = not self.san_interface.runmode
        if 'cachesize' in self._updatedattr or _load:
            if self.cachesize > 0:
                if self.raid == RaidLevel.dr:
                    self.cachesize=0
                    return (1,'cache over dr raid is not supported')
                (e,pt) = ext2path(self)
                if e:
                    return (e,'Error updating cache for raid, %s' % pt)
                # we force the cache because volume name could be different
                # after reboot. e.g. /dev/md1 instead of /dev/md2
                (e,r) = self.provider.add_cache(pt, self.cachesize, force=True)
                if e:
                    if not _load:    # reset cachesize on create but not on load
                        self.cachesize=0
                    return (e,'Error adding cache for raid, %s' % r)
            else:
                if self.cachepresent or self.cachedict:
                    (e,r) = self._remove_md_raid_cache()
                    if e:
                        return (e,'Error removing cache from raid, %s' %r)
        return (0,'')

    def _remove_md_raid_cache(self):
        """
        The description of _remove_md_raid_cache comes here.
        @return
        """
        logger.eventlog.debug('removing cache from %s' % str(self))
        e,r = self.provider.del_cache(self,destroy=True)
        if e:
            return (e, 'Error removing cache from raid, %s' % r)
        return (0,'')

    def _update_dr_raid(self,flags='',pvd=None):
        """
        The description of _update_dr_raid comes here.
        @param flags
        @param pvd
        @return
        """
        if not self.devices:
            # create device list from slave objects, in recovery state
            self.devices = [d.extent for d in self.slaves() if d.extent]
        if self.devices:
            if len(self.devices) <> 2:
                return (1,'must have at exactly 2 devices (specified by the devices property) to form a replica')
            if (self.devices[0].exttype == 'physical' and len(self.devices[0].paths) > 1) or \
            (self.devices[1].exttype == 'physical' and len(self.devices[1].paths) > 1):
                return (1, 'cant use devices with multiple paths')

            if not IsRunning(self.devices[0]) or not IsRunning(self.devices[1]):
                return (1,'cant add raid with the current devices state')

            delta = abs(self.devices[0].size - self.devices[1].size) + 0.0
            # check if delta is not greater than 5%
            if delta / self.devices[0].size > 0.05:
                return (1,'DR devices need to be about the same size')

            tmp=[d.name for d in self.devices]
            print 'create drbd %s devs: %s' % (self.name,','.join(tmp))

            (e,pt0)=ext2path(self.devices[0])
            if e:
                return (e,'cant add Raid slave %s, ' % str(self.devices[0])+pt0)
            pvd0=pt0.provider

            (e,pt1)=ext2path(self.devices[1])
            if e:
                return (e,'cant add Raid slave %s, ' % str(self.devices[1])+pt1)
            pvd1=pt1.provider

            if pvd0 is pvd1:
                return (1,'the 2 DR slaves are in the same provider (%s), and must reside on different ones' % pvd0.name)
            if pvd and not (pvd is pvd0 or pvd is pvd1) :
                # this raid is not related to the provider we are updating (pvd<>None)
                return (0,'not me')

            ips=self.san_interface.calc_ippath(pvd0,pvd1)
            if not ips:
                return (1,'no path between the 2 providers')

            _loadonly=self.loadonly
            _primary=(not self.provider or pvd0==self.provider)
            # when provider is not set choose the lower size disk
            if not self.provider and self.devices[0].size > self.devices[1].size:
                _primary = False
            print 'paths: ',str(pt0),str(pt1)
            (e1,r1)=pvd0.config_drbd(self.name,self.idx,ips[0],ips[1],pt0,pt1,primary=_primary,loadonly=_loadonly)
            print 'config_drbd1:',e1,r1
            if e1:
                if not _loadonly:
                    pvd0.remove_drbd(self.name)
                return (1,'failed to configure DR on provider %s,' % pvd0.name +r1)
            (e2,r2)=pvd1.config_drbd(self.name,self.idx,ips[1],ips[0],pt1,pt0,primary=not _primary,loadonly=_loadonly)
            print 'config_drbd2:',e2,r2
            if e2:
                if not _loadonly:
                    pvd0.remove_drbd(self.name)
                    pvd1.remove_drbd(self.name)
                return (1,'failed to configure DR on provider %s,' % pvd1.name +r2)
            self.devices=[]
            self.solve_split_brain()
        return (0,'')

    def _update_params(self):
        """
        The description of _update_params comes here.
        @return
        """
        if self.raid == RaidLevel.dr:
            return
        _load = not self.san_interface.runmode
        params = {}
        if ('readahead' in self._updatedattr or _load) and self.readahead:
            params['readahead'] = self.readahead
        if params:
            for slave in self.slaves():
                ext = slave.extent
                #if Sanplunisinstance(ext, Sanplun):
                if ext.get_object_type() == 'Sanplun':
                    for pt in ext.paths():
                        pt.provider.set_dev_params(pt,params)
                else:
                    ext.provider.set_dev_params(ext,params)
            self.provider.set_dev_params(self,params)

    def update(self,flags='',pvd=None):
        """
        The description of update comes here.
        @param flags
        @param pvd
        @return
        """
        if self.state == ObjState.created:
            self.manual = True
        self._update_params()
        (e,r) = (0,'')
        if self.raid != RaidLevel.dr:
            (e,r) = self._update_md_raid(flags,pvd)
        elif self.raid == RaidLevel.dr: # TBD add case for update on pvd recover
            (e,r) = self._update_dr_raid(flags,pvd)
        if e:
            return (e,r)
        e,r = self._update_raid_cachesize()
        if e:
            return (e,r)
        return (0,'')

    def show(self,mode=0,level=0,ident=''):
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        if self.locked : l='L'
        else : l=' '
        r='Raid:%-8s' % self.raid
        tmp='%sg%-3d %s %-12s %-8s %s Volumes:%d Size:%s Used:%s' % \
           (ident,self.idx,l,self.name,self.state,r,len(self.slaves),printsz(self.size),printsz(self.totused))
        if level>0:
            tmp+='\n'+ident+'   Slaves:'
            for p in self.slaves.values()  : tmp+='\n'+p.show(mode,level-1,ident+'    ')
            tmp+='\n'
        return tmp

    def export(self,san,path,canadd=True):
        """
        The description of export comes here.
        @param san
        @param path
        @param canadd
        @return
        """
        if self.auto : canadd=False
        return SanBase.export(self,san,path,canadd)

