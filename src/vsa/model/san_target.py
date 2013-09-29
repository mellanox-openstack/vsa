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


from vsa.model import volstr2obj
from vsa.model.san_base import SanBase
from vsa.infra.params import Transport, ObjState, paramopts, iSCSIOpts, RaidLevel,\
    ReqState
from vsa.model.vsa_collections import VSACollection, RefDict
from vsa.model.target import TargetLun
from vsa.model.tmp_vol import TmpVol
from vsa.infra.infra import getnextspace, tstint
from vsa.infra import logger
from vsa.model.san_container import SanContainer

class SanTarget(SanBase):
    child_obj=['luns','sessions']
    add_commands=['luns'] # TBD add portals
    set_params=['server','volumes','transport','pid','iscsiopt','vparams','migrate'] # TBD add ,'portal'
    newonly_fields=['transport','volumes']
    #show_columns=['Idx','Name','Server','Transport','Provider','Luns','Sessions']
    #ui_buttons=[add_btn,del_btn,migrate_btn,extmon_btn]

    def __init__(self,name,dev=None):
        """
        The description of __init__ comes here.
        @param name
        @param dev
        @return
        """
        SanBase.__init__(self,name,'SAN Target')
        self.device=dev
        self.updateflag=0
#        self.iscsiname=iscsiname
        self.auto=False
        self.transport=Transport.iscsi
        self.portal=None
        self.id=0
        self.pid=0
        self.luns=VSACollection(TargetLun,self,'luns',True,desc='Storage LUNs',icon='vm_g.png')
        self.server=None
        self.redirect=False
        self.redir_tid=0
        self.canmigrate=False
        self.initiators={}
        self.vparams={}
        self.iscsiopt=self.san_interface.general.iscsiopt
        self.iscsioptrd={}
        self.acls=[]
        self.users=[]
        self.volumes=[]
        self.tmppvd=None
        self.volsign=''
        self.icon=""
        self.sessions = RefDict(None, self, 'sessions', desc='Client Sessions', icon='hard_disk.png', cols=['itn','initiator','IP'],
                    table=lambda self:[[k]+self.initiators[k] for k in self.initiators.keys()])

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.id, self.name, getattr(self.server, 'name', ''), self.transport,
            getattr(self.device, 'name', '') + ':p' + str(self.pid),
            len(self.luns), len(self.initiators)]

    def set_server(self,san,key,val='',test=0):
        """
        The description of set_server comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        #srvlist = san.servers.keys()
        srvlist = self.san_interface.servers.keys()
        if val not in srvlist:
            return (1,'server name %s does not exist, please specify a valid name' % val)
        if self.initiators and self.san_interface.runmode:
            return (1,'cannot change server name, initiators are connected')
        if test:
            return (0,'')
        if self.server and self.server.targets.has_key(self.name):
            del self.server.targets[self.name]
        self.server = self.san_interface.servers[val]
        self.server.targets[self.name] = self
        return (0,'')

    def get_server(self,san,key):
        """
        The description of get_server comes here.
        @param san
        @param key
        @return
        """
        if self.server:
            return (0,self.server.name)
        return (0,'')

    def set_pid(self,san,key,val='',test=0):
        """
        The description of set_pid comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        if val == str(self.pid):
            return (0,'')
        if self.state <> ObjState.created:
            return (1,'Cannot change pid for running targets')
        if self.device:
            max_pid = self.device.tgtprocs - 1
        else:
            max_pid = 0
        return self.san_interface.robots.set_int(self,key,val,test,0,max_pid)

    def set_vparams(self,san,key,val='',test=0):
        """
        The description of set_vparams comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        return self.san_interface.robots.set_strdict(self,key,val,test,paramopts)

    def set_iscsiopt(self,san,key,val='',test=0):
        """
        The description of set_iscsiopt comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        return self.san_interface.robots.set_strdict(self,key,val,test,iSCSIOpts)

    def set_volumes(self,san,key,val='',test=0):
        """
        The description of set_volumes comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        dl=val.split(';')
        vols=[]
        first=True
        tmppvd=None
        hasdr=False
        for d in dl:
            (e,t,v)=volstr2obj(d,pvdin=self.device, san=self.san_interface)
            if e:
                return (e,t)
            obj=TmpVol()
            obj.devtype=t
            if t in 'ntf':
                obj.devstr=v[0]
                if not self.device and first:
                    tmppvd=v[1]
                    first=False
                elif tmppvd and not (tmppvd is v[1]):
                    return (1,'volume strings points to different providers ')
            else:
                obj.volume=v
                if v.exttype=='raid' and v.raid==RaidLevel.dr:
                    hasdr=True
            vols+=[obj]
        if (len(vols) > 1 or len(self.luns) > 0) and hasdr:
            return (1,'can only have one LUN per target when using DR Raid type (cluster mirror)')
        if not test:
            self.volumes=vols
            self.tmppvd=tmppvd
        return (0,'')

    def add_luns(self,lun=None,volume=None):
        """
        The description of add_luns comes here.
        @param lun
        @param volume
        @return
        """
        if not lun or lun=='#':
            lun=str(getnextspace(self.luns.keys(),1))
        else:
            if tstint(lun) < 0:
                logger.eventlog.error('can not add LUN to %s, illegal LUN number %s' % (self.name,lun))
                return None
        return self.luns.add(lun,TargetLun(self,lun,vol=volume))

    def _find_migration_targets(self):
        """
        The description of _find_migration_targets comes here.
        @return
        """
        # test if we can migrate this target, 1st case physical disks with multipath (e.g. FC gateway case)
        all_physical = True
        pvdrank = {}
        for l in self.luns():
            if l.id <> 0:
                if l.volume and l.volume.exttype == 'physical':
                    for pt in l.volume.paths():
                        # find which providers have a valid path to that disk and
                        # add 1 to it (for ranking)
                        # exclude non running paths or paths that point to the existing
                        # provider for this target
                        if pt.state == ObjState.running and pt.reqstate == ReqState.enabled \
                        and not (self.device and self.device is pt.provider):
                            if pvdrank.has_key(pt.provider.name):
                                pvdrank[pt.provider.name] += 1
                            else:
                                pvdrank[pt.provider.name] = 1
                else:
                    all_physical = False
        print 'Target migrate test for %s: all_physical: %s, pvdrank: %s' % (self.name, str(all_physical), str(pvdrank))
        return (all_physical, pvdrank)

    def migrate(self,newpvd='',b=''):
        """
        The description of migrate comes here.
        @param newpvd
        @param b
        @return
        """
        # test if we can migrate this target, 1st case physical disks with multipath (e.g. FC gateway case)
        (all_physical, pvdrank) = self._find_migration_targets()
        dr_case = False

        #
        # check if possible to migrate
        #

        if all_physical:
            # physical disk luns with valid alternate paths
            if not pvdrank:
                return (1, 'no alternative paths for migration')
            if newpvd and newpvd not in pvdrank.keys():
                return (1, 'Cannot migrate, Provider name %s not a valid migration target or doesnt exist' % newpvd)
            # TODO select the best provider (rank), for now we just choose the first in the list of options
            if not newpvd:
                newpvd = pvdrank.keys()[0]
            # TODO handle case for replicated cache: remove cache (old), promote, load cache (new)
        else:
            if len(self.luns) <> 2 or not (self.luns['1'].volume and \
            self.luns['1'].volume.exttype == 'raid' and self.luns['1'].volume.raid == RaidLevel.dr):
                return (1, 'must have one LUN which is a dr Raid object or physical disks with multiple paths')
            #
            # drbd case
            #
            dr_case = True
            dr_vol = self.luns['1'].volume
            candidates = dr_vol.get_dr_candidates(dr_vol.provider)
            if not candidates:
                return (1, 'there are no alternate/valid migration targets at this point')
            pvdlist = [s.provider.name for s in candidates]
            if newpvd and newpvd not in pvdlist:
                return (1, 'Cannot migrate, Provider name %s not a valid migration target or doesnt exist' % newpvd)
            if not newpvd:
                newpvd = pvdlist[0]

        #
        # start migration
        #

        # delete target from tgtd and change state to created
        if self.state <> ObjState.created:
            self.state = ObjState.created
            if self.san_interface.general.iscsiredirect and not (self.device is self.san_interface.lclprovider):
                self.san_interface.lclprovider.del_target(self,True)
            (e,txt) = self.device.del_target(self,force=True)
            if e:
                logger.eventlog.error('Cannot delete target %s on %s during migrate op, Err: %s' % (self.name,str(self.device),str(txt)))
            for l in self.luns():
                if l.id <> 0:
                    l.state = ObjState.created

        # handle multipath cache: remove old cache
        mpcvols = []
        if all_physical:
            for l in self.luns():
                if l.id <> 0:
                    if l.volume.cachepresent:
                        self.device.del_cache(l.volume,destroy=False)
                        mpcvols += [l.volume]
                        # promote drbd
                        l.volume.cachedrdev.promote_one(checkluns=False,exclude=self.device)

        if dr_case:
            # handle drbd case
            self.device = None
            for s in dr_vol.slaves():
                if s.provider and s.provider.name == newpvd:
                    s.promote(checkluns=False)
        else:
            self.device = self.san_interface.providers[newpvd]

        # multipath cache: update volumes to load cache
        for v in mpcvols:
            logger.eventlog.debug("calling volume update on %s" % str(v))
            v.update()

        for l in self.luns():
            if l.id <> 0:
                (e,txt) = l.update()
                if e:
                    logger.eventlog.error('Migrate, Lun update error: Lun %d ,' % l.id + txt)
        return (0,'')

    def show(self,mode=0,level=0,ident=''):
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        srv=''; dev='';
        if self.server : srv=self.server.name
        if self.device : dev=self.device.name
        tmp = '%s%s:%-35s p%dt%-3d %-5s Luns: %-3d Server: %-8s' % \
           (ident,dev,self.name,self.pid,self.id,str(self.transport),len(self.luns),srv)
        if level>0:
            tmp+='\n'+ident+'  LUNs:'
            for k in sorted(self.luns.keys())  : tmp+='\n'+self.luns[k].show(mode,level-1,ident+'    ')
            tmp+='\n'+ident+'  Connections:'
            for l in self.initiators.values()  : tmp+='\n    '+ident+':'.join(l)
            tmp+='\n'
        return tmp

    def update(self,flags='',nest=False):
        """
        The description of update comes here.
        @param flags
        @param nest
        @return
        """
        if self.state == ObjState.created and not nest:
            # nest is True when target.update is called from lun.update, this is to avoid endless loop
            for v in self.volumes:
                print 'Volume: ',str(v.volume),' devstr: ',str(v.devstr),' pvd: ',str(getattr(v.volume,'provider',None))
                if v.volume and self.device and not (self.device is getattr(v.volume,'provider',self.device)) :
                    return (1,'Error, Volume %s is not in the same provider as this target (%s) ' % (str(v.volume),self.device.name))
                l = self.add_luns(lun=None,volume=v.volume)
                if not l or isinstance(l,str):
                    return (1,'Error adding Lun (volume %s), ' % str(v.volume)+str(l))

                if not v.volume:
                    l.devstr=v.devstr
                    l.devtype=v.devtype
                    l.tmppvd=self.tmppvd

                (e,txt) = l.update(refresh=0)
                if e:
                    return (e,'Target error: Lun %d ,' % l.id + txt)
            self.volumes=[]

            for l in self.luns():
                if l.state == ObjState.created:
                    l.update(refresh=0)

        print 'update target: %s dev: %s  Tstate: %s uf: %d redir: %s #1' % (self.name,str(self.device),str(self.state),self.updateflag,str(self.redirect))
        print 'lclpvd: ',str(self.san_interface.lclprovider),' luns: ',str(self.luns.keys()),' nest: ',nest

        if self.device:
            if self.pid >= self.device.tgtprocs:
                return (1,'Target pid is not valid (too high)')
            self.updateflag=0
            self.device.load_targets(pid=self.pid)

            if self.device.state != ObjState.running:
                logger.eventlog.error('Target update error, Provider %s cannot be configured, not running (State=%s)' % (self.device.name,str(self.device.state)))
                return (1,'Provider %s cannot be configured, not running (State=%s)' % (self.device.name,str(self.device.state)))
            if self.state==ObjState.created or self.updateflag==0:
                if not self.server:
                    self.server=self.san_interface.servers['everyone']
                print 'add target: %s in %s' % (self.name,str(self.device))
                self.device.add_target(self,self.name,self.server,self.vparams)
##                for lun in self.luns() : lun.state=ObjState.created
                if self.san_interface.general.iscsiredirect and not (self.device is self.san_interface.lclprovider):
                    print 'add redir: %s in %s' % (self.name,str(self.san_interface.lclprovider))
                    self.san_interface.lclprovider.add_target(self,self.name,self.server,self.vparams,self.san_interface.general.redirectcb)
##                for l in self.luns.values()[1:]: l.update(refresh=0)
            else:
                print 'update target: %s in %s' % (self.name,str(self.device))
                self.device.update_target(self,self.server,self.vparams)
                if self.san_interface.general.iscsiredirect and not (self.device is self.san_interface.lclprovider):
                    if self.redirect:
                        print 'update redir: %s in %s' % (self.name,str(self.san_interface.lclprovider))
                        self.san_interface.lclprovider.update_target(self,self.server,self.vparams)
                    else:
                        print 'add redir: %s in %s' % (self.name,str(self.san_interface.lclprovider))
                        self.san_interface.lclprovider.add_target(self,self.name,self.server,self.vparams,self.san_interface.general.redirectcb)
            if not nest:
                for k,l in self.luns.items():
                    if l.id > 0:
                        (e,txt)=l.update(refresh=0)
                        if e:
                            return (e,'Target error: Lun %d ,' % l.id + txt)

            if self.iscsiopt or self.san_interface.general.iscsiopt:
                opt={}
                hasnew=False
                for k,v in self.san_interface.general.iscsiopt.items():
                    opt[k]=v
                for k,v in self.iscsiopt.items():
                    opt[k]=v
                for k,v in opt.items():
                    if not self.iscsioptrd.has_key(k) or self.iscsioptrd[k] <> v:
                        hasnew=True
                        break
                if hasnew:
                    self.device.set_tgopt(self,opt)
##            self.device.load_targets()
##        self._flush()
        return (0,'')

    def delete(self,force=False):
        """
        The description of delete comes here.
        @param force
        @return
        """
        if (self.name.startswith('iqn.vsa.vhba.') or  self.name.startswith('iqn.vsa.vdisk.')) and not force:
            return (1, 'target is an Auto generate vHBA or vDisk, delete the vHBA/vDisk or use force')
        # TBD if generated from vHBA , clean the vHBA.targets object
        if len(self.luns) > 1 and not force:
            return (1, 'target %s has LUNs, remove LUNs first or use force option' % self.name)
        if self.state != ObjState.created:
            self.state = ObjState.delete
            (e,txt) = self.device.del_target(self,force)
            if e:
                return (e,txt)
            if self.san_interface.general.iscsiredirect and self.device is not self.san_interface.lclprovider:
                self.san_interface.lclprovider.del_target(self, force)
            for lun in self.luns.values():
                if lun.id <> 0:
                    self.luns.delete(lun, force=True, skipdel=True)
                if lun.volume and lun in lun.volume.usedinluns:
                    lun.volume.usedinluns.remove(lun)
                    print 'removed from used in LUNs list for %s' % str(lun.volume)
        if self.server and self.server.targets.has_key(self.name):
            del self.server.targets[self.name]
        return (0,'')

    def export(self,san,path,canadd=True):
        """
        The description of export comes here.
        @param san
        @param path
        @param canadd
        @return
        """
        if self.auto:
            return []
        return SanBase.export(self, self.san_interface, path, canadd, ['volumes'])

