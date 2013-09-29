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


from vsa.model.san_base import SanBase
from vsa.model.alarm import AlarmsCls
from vsa.model.general_prop import GeneralProp
from vsa.client.robots import Robots
from vsa.model.vsa_collections import VSACollection
from vsa.model.san_raid_group import SanRaidGrp
from vsa.model.san_vol_group import SanVolgrp
from vsa.model.server_group import ServerGroup
from vsa.model.san_target import SanTarget
from vsa.model.fc import FCport
from vsa.model.provider import Provider
import os
from vsa.infra.params import ObjState, RaidLevel
from vsa.infra import logger
from vsa.client.gui.jsTree import jsTree
from vsa.infra.infra import getunique, getnextspace
import random
from vsa.model import BuildSANTree
from vsa.model.sanp_lun import Sanplun

from vsa.model.san_container import SanContainer


class SanResources(SanBase):
    child_obj=['general','providers','fcports','disks','raids','pools','servers','targets','alarms']
    add_commands=['disks','targets','servers','providers','raids','pools']
    set_params=['date','debuglvl']

    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        #First set the container instance, because called from SanBase.__init__
        SanContainer.getInstance().set_san(self)
        SanBase.__init__(self,'SAN','SAN Fabric')
        self.fullpath=''
        self.runmode=False
        self.postdisks=False
        self.newfcpaths=[]
        self.debug=True
        self.wwnspace=[]
        self.wwpnspernode=4
        self.volidx={}
        self.lclprovider=None
        self.post_init()

    def post_init(self):
        """

        """
        logger.eventlog.debug("post_init")
##        self.cache=CacheMngr()
        self.alarms = AlarmsCls()
        self.general = GeneralProp()
        self.robots = Robots()

        self.disks = VSACollection(Sanplun, self, 'disks', True, altidx='idx',
                indexed=True, desc='Physical Disks', icon='hard_disk.png')
        logger.eventlog.debug("loading disks")
        # physical LUNs

        self.raids = VSACollection(SanRaidGrp, self, 'raids', True, altidx='idx',
                        indexed=True, desc='Raid and DR Groups', icon='storage_g.png')
        logger.eventlog.debug("loading raids")

        self.pools = VSACollection(SanVolgrp, self, 'pools', True,
                            desc='Storage Pools', icon='storage_g.png')
        logger.eventlog.debug("loading pools")
        # Volume Groups

        self.targets = VSACollection(SanTarget, self, 'targets', True,
                            desc='Storage Targets', icon='storage_g.png')
        logger.eventlog.debug("loading targets")

        self.fcports = VSACollection(FCport, self, 'fcports', True,
                                  desc='FC Ports', icon='VirtIfc_g.png')
        logger.eventlog.debug("loading fcports")

        self.providers = VSACollection(Provider, self, 'providers', True,
                                desc='VSA Storage Providers', icon='computer_g.png')
        logger.eventlog.debug("loading providers")
        # storage targets/routers

        self.servers = VSACollection(ServerGroup, self, 'servers', True,
                        desc='Servers (Initiators)', icon='logicalserver_g.png')
        logger.eventlog.debug("loading servers")

        ev = ServerGroup('everyone', self.general.defaultos, ['ALL'])
        self.servers.add('everyone', ev)
        ev.wwnn = self.general.basewwn
        ev.update()
        self.__load_defaults()

    def __load_defaults(self):
        """
        The description of __load_defaults comes here.
        @return
        """
        self._defaults = {}
        p = os.path.dirname(os.path.abspath(__file__)) + '/'
        lines = open(p + 'objdef.db').readlines()
        for l in lines:
            ll = l.split()
            if len(ll) == 2:
                self._defaults[ll[0]] = ll[1]

    def calc_ippath(self,fpvd,tpvd):
        """
        The description of calc_ippath comes here.
        @param fpvd
        @param tpvd
        @return
        """
        sortnets = sorted(fpvd.ifs(), key=lambda i: i.speed,reverse=True)
        for f in sortnets:
            for t in tpvd.ifs():
                if t.state == ObjState.running and (not t.isvirtual) and (not f.isvirtual) and f.state==ObjState.running and f.data and f.ip in t.subnet():
                    return [f.ip,t.ip]
        return []

    def setobj(self,obj,key,val='',test=0,force=False):
        """
        The description of setobj comes here.
        @param obj
        @param key
        @param val
        @param test
        @param force
        @return
        """
        return self.robots.setobj(obj,key,val,test,force)

    def getobj(self,obj,key):
        """
        The description of getobj comes here.
        @param obj
        @param key
        @return
        """
        (e,v)=self.robots.getobj(obj,key)
        if e :
            logger.eventlog.warning(v)
            raise Exception()
        return v

    def export(self,san=None,path=''):
        """
        The description of export comes here.
        @param san
        @param path
        @return
        """
        out=[]
        for i in self.set_params :
            if i not in ['date','debug','debuglvl']:
                isdir = getattr(self,i).__class__.__name__=='dict'
                if isdir : out += ["set /%s %s" % (i,self.getobj(self,i))]
                else : out += ["set / %s=%s" % (i,self.getobj(self,i))]
        for c in self.child_obj :
            out+=self.__dict__[c].export(self,'/'+c)
        return out

    def after_load(self):
        """
        The description of after_load comes here.
        @return
        """
        print 'after load'
        self.runmode=True
        if not self.postdisks : # will be triggered on the first load
            self.postdisks=True
            self.before_targets_load()

    def before_targets_load(self):
        """
        The description of before_targets_load comes here.
        @return
        """
        print 'before_targets_load'
        for r in self.raids(): r.promote_one()

    def BuildTree(self):
        """
        The description of BuildTree comes here.
        @return
        """
        root=jsTree()
        BuildSANTree(self,root)
#        print root.GetTree()
        return root

    def add_provider(self, name, url='localhost:8055', usr='root', pwd='123456'):
        """
        The description of add_provider comes here.
        @param name
        @param url
        @param usr
        @param pwd
        @return
        """
        pvd = Provider(self, name, url, usr, pwd)
        self.providers.add(name, pvd)
        pvd.load(info=False, sync=True)
        return pvd

    def add_disks(self,guid,name='',manual=True):
        """
        The description of add_disks comes here.
        @param guid
        @param name
        @param manual
        @return
        """
        if not name:
            name = guid
        if name in self.disks.keys():
            return None
        if manual and self.runmode:
            return 'cannot manually add a disk'
        tmplun = Sanplun(guid,name)
        self.disks.add(tmplun.guid,tmplun)
        return tmplun

    def add_raids(self,name,provider=None,needpvd=True, firstidx=0):
        """
        The description of add_raids comes here.
        @param name
        @param provider
        @param needpvd
        @param firstidx
        @return
        """
        if name in self.raids.keys() : return None
        if not name or name=='#': name=getunique(self.raids.keys(),'raid')
        if ':' in name and not provider and needpvd:
            pvd=name.split(':')[0]
            if not self.providers.has_key(pvd):
                return 'provider name %s not found' % pvd
            provider=self.providers[pvd]
        if not provider and needpvd and len(self.providers)==1 :
                provider=self.providers.values()[0]
        spl=SanRaidGrp(name,provider)
        return self.raids.add(name,spl,firstidx)

    def add_pools(self,name,provider=None,needpvd=True):
        """
        The description of add_pools comes here.
        @param name
        @param provider
        @param needpvd
        @return
        """
        if name in self.pools.keys() : return None
        if not name or name=='#': name=getunique(self.pools.keys(),'pool')
        vg=SanVolgrp(name,provider)
        return self.pools.add(name,vg)

    def add_targets(self,name,provider=None):
        """
        The description of add_targets comes here.
        @param name
        @param provider
        @return
        """
        # not setting provider, will be done w first LUN
        if not self.postdisks : # will be triggered on the first load
            self.postdisks=True
            self.before_targets_load()
##        if not provider and len(self.providers)==1 :
##                provider=self.providers.values()[0]
        if name.startswith('#'):
            nlen=len(name.strip())
            if provider:
                name='iqn.vsa.'+provider.name+'.'+name[1:]
                if nlen==1:
                    name=getunique(self.targets.keys(),name+'target')
            else:
                name='iqn.vsa.'+name[1:]
                if nlen==1:
                    name=getunique(self.targets.keys(),name+'target'+str(random.randint(0,9999)))
        if not name:
            name = getunique(self.targets.keys(),'iqn.vsa.target'+str(random.randint(0,9999)))
        if name in self.targets.keys():
            return None
        tmp=SanTarget(name,provider)
        return self.targets.add(name,tmp)

    def add_servers(self,name=''):
        """
        The description of add_servers comes here.
        @param name
        @return
        """
        if name in self.servers.keys() : return None
        if not name or name=='#': name=getunique(self.servers.keys(),'srv')
        tmp=ServerGroup(name)
        nxw=getnextspace(self.wwnspace)
        tmp.wwnn='%16.16X' % (int(self.general.basewwn,16)+nxw*self.wwpnspernode)
        self.wwnspace+=[nxw]
        return self.servers.add(name,tmp)

    def debuglvl(self,lvl='',b='',c='',d=''):
        """
        The description of debuglvl comes here.
        @param lvl
        @param b
        @param c
        @param d
        @return
        """
        if not lvl or lvl=='1' or lvl.lower()=='true' :
            loglevel=logger.logging.DEBUG
            self.debug=True
        else :
            loglevel=logger.logging.INFO
            self.debug=False
        logger.eventlog.setLevel(loglevel)

    def date(self,a='',b='',c='',d=''):
        """
        The description of date comes here.
        @param a
        @param b
        @param c
        @param d
        @return
        """
        if a=='' : return
        val=(a+' '+b+' '+c+' '+d).strip()
        for p in self.providers.values():
            r=p.set_date(val)
            print r

    def reboot(self,pvd='',force=''):
        """
        The description of reboot comes here.
        @param pvd
        @param force
        @return
        """
        if pvd and not self.providers.has_key(pvd) : # TBD log error
            return
        if pvd :
            return self.providers[pvd].reboot(force)
        else :
            for p in self.providers.values():
                if p.name<>self.lclprovider.name :
                    p.reboot(force)
            return self.lclprovider.reboot(force)

    def refresh(self, provider=None):
        """
        The description of refresh comes here.
        @param provider
        @return
        """
        if provider:
            provider.load()
        else:
            for p in self.providers.values():
                p.load()

    def load_finished(self, pvd_name):
        """
        The description of load_finished comes here.
        @param pvd_name
        @return
        """
        '''
        Load finish callback.
        Called by every provider at the end of the load.
        @param pvd_name: provider name
        '''
        #logger.eventlog.debug('%s finished loading' % pvd_name)
        for pvd in self.providers.values():
            if pvd.loading:
                return

        self.__check_dr_devices()
        # All providers finished the load
        self.refresh_finished()

    def __check_dr_devices(self):
        """
        The description of __check_dr_devices comes here.
        @return
        """
        for dr in self.raids():
            if dr.raid == RaidLevel.dr:
                promote=True
                for slave in dr.slaves():
                    if slave.state == ObjState.running:
                        if slave.role == 'primary':
                            promote=False
                            break
                if promote:
                    logger.eventlog.debug('Trying to promote dr raid %s' % dr.name)
                    dr.promote_one(checkluns=False)

    def refresh_finished(self):
        """
        The description of refresh_finished comes here.
        @return
        """
        '''
        Refresh finish callback.
        '''
        #logger.eventlog.debug('Refresh finished')
        for pvd in self.providers.values():
            # pvd name isn't periodically updated but fullname is
            if pvd.fullname and pvd.name != pvd.fullname.split('.')[0]:
                logger.eventlog.warning('Provider %s introducing itself as %s' % (pvd.name, pvd.fullname))
            # deal with provider that was re-discovered/recovered
            if pvd.state==ObjState.running and pvd.wasabsent :
                self.reconfig_provider(pvd)
                pvd.wasabsent=False
            # deal with provider that failed (become absent)
            if pvd.state==ObjState.absent and not pvd.wasabsent:
                logger.eventlog.info('Evacuating Provider: '+pvd.name+' (running->absent)')
                pvd.evacuate()

        for tg in self.targets() :
            if tg.device and tg.device.state==ObjState.running:
                if tg.state==ObjState.absent:
                    logger.eventlog.info('re-create/update target %s on %s (was absent)' % (tg.name,tg.device.name))
                    tg.update()
                else:
                    for lun in tg.luns():
                        if lun.state == ObjState.absent:
                            tg.device.del_lun(tg,lun.id,force=True)
                            lun.state = ObjState.created
                            lun.update()

        # reconfigure/update vHBAs
        if self.general.hbarefresh :
            for srv in self.servers() :
                for vhba in srv.hbas() :
                    if vhba.name in self.newfcpaths :
                        vhba.update_async(False)
            self.newfcpaths=[]

    def reconfig_provider(self, provider=None):
        """
        The description of reconfig_provider comes here.
        @param provider
        @return
        """
        '''
        re apply policy on a provider in case of recovery
        '''
        print 'Reconfig provider: %s' % provider.name
        logger.eventlog.info('Reconfig provider: %s' % provider.name)
        # disks and paths
        self.reconfigDisks(provider)
        # raids
        self.reconfigRaids(provider)
        # pools
        self.reconfigPools(provider)
        # targets and luns
        self.reconfigTargets(provider)
        # servers
        self.reconfigServers(provider)


    def reconfigServers(self, provider):
        """
        The description of reconfigServers comes here.
        @param provider
        @return
        """
        for srv in self.servers():
            # TBD vDisk & vHBA
            pass

    def reconfigTargets(self, provider):
        """
        The description of reconfigTargets comes here.
        @param provider
        @return
        """
        for tg in self.targets():
            if tg.device and (tg.device is provider):
                print 're-create/update target on pvd absent->running : ',tg.name
                tg.update()
            elif tg.state == ObjState.created:
                print 'try to re-create/update target: %s' % tg.name
                tg.update()

    def reconfigDisks(self, provider):
        """
        The description of reconfigDisks comes here.
        @param provider
        @return
        """
        for disk in self.disks():
            paths = [pt for pt in disk.paths() if pt.provider is provider]
            if paths:
                disk.update(flags='f')

    def reconfigRaids(self, provider):
        """
        The description of reconfigRaids comes here.
        @param provider
        @return
        """
        for raid in self.raids():
            raid.update(pvd=provider)

    def reconfigPools(self, provider):
        """
        The description of reconfigPools comes here.
        @param provider
        @return
        """
        for pool in self.pools():
            pass

    def rescan(self,pvd='',host=''):
        """
        The description of rescan comes here.
        @param pvd
        @param host
        @return
        """
        if pvd and not self.providers.has_key(pvd) : # TBD log error
            return (1,'no such provider')
        if pvd : return self.providers[pvd].rescan(host)
        else :
            for p in self.providers.values():
                p.rescan()
            return (0,'')
