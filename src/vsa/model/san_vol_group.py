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


from vsa.model.extent import Extent
from vsa.model.vsa_collections import VSACollection
from vsa.infra.params import RaidLevel, QualityType, ObjState
from vsa.model.pool import VolGrpItem, VolGrpSubpool
from vsa.model.san_volume import SanVolume
from vsa.model import volstr2obj, obj2volstr, ext2path
from vsa.model.san_base import SanBase
from vsa.infra.infra import iif, printsz, getunique

class SanVolgrp(Extent):
    child_obj=['slaves','volumes','subpools']
    add_commands=['volumes']
    set_params=['reqstate','glbl','quality','raid','chunk','devices','readahead','vparams']
    newonly_fields=['chunk','raid','provider','glbl']
    #show_columns=['Name','Size','Used','Free','PVs','LVs','Raid','Provider','attr','Quality','Chunk']
    #ui_buttons=[add_btn,del_btn,addlv_btn,addisk_btn]

    def __init__(self,name='',provider=None,raid=RaidLevel.none,devs=[],glbl=False):
        """
        The description of __init__ comes here.
        @param name
        @param provider
        @param raid
        @param devs
        @param glbl
        @return
        """
        Extent.__init__(self,'',name,'Storage Pool')
        self.exttype='pool'
        self.provider=provider
        self.glbl=glbl  #  pool spans across providers
        self.slaves=VSACollection(VolGrpItem,self,'slaves',desc='Physical Volumes (PV)',icon='hard_disk.png')
        self.volumes=VSACollection(SanVolume,self,'volumes',True,desc='Logical Volumes',icon='vm_g.png')        # virtual LUNs
        self.raid=raid # '0' '1' '5' '6' '10' 'multipath' 'dr'
        self.quality=QualityType.unknown
        self.chunk=0
        self.free=0
        self.attr=''
        self.subpools=VSACollection(VolGrpSubpool,self,'subpools',True,desc='Sub-pool',icon='vm_g.png')
        self.devices=devs
        self.devsign=''
        self.manual=False
        self.raidgrp=None
        self._flush()

    def find_space(self,size,dr=False):
        """
        The description of find_space comes here.
        @param size
        @param dr
        @return
        """
        reserved = self.san_interface.general.reserved_vgspace
        if self.glbl:
            pvdnum=iif(dr,2,1)
            pvds=[]
            # TBD add sorting to find least used sub-VG, add DR support
            for sp in self.subpools():
                used = sp.size-sp.free
                if sp.size*(100-reserved)/100 >= used+size:
                    pvds+=[sp.provider]
                    if len(pvds)>=pvdnum:
                        return (0,pvds)
        else:
            if self.size*(100-reserved)/100 >= self.totused+size:
                return (0,[self.provider])
        return (1, 'no available space for cache. note that %d%% are reserved.' % reserved)

    def __free_space(self):
        """
        The description of __free_space comes here.
        @return
        """
        reserved = self.san_interface.general.reserved_vgspace
        if self.glbl:
            free=0
            for sp in self.subpools():
                used = sp.size-sp.free
                free += (sp.size*(100-reserved)/100 - used)
        else:
            free = self.size*(100-reserved)/100 - self.totused
        return free

    free_space = property(__free_space)

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        if self.glbl : pv='GLOBAL'
        else : pv=getattr(self.provider,'name','')
        (sz,fr,us)=self._getsizes()
        return [self.name,printsz(sz),printsz(us),printsz(fr),len(self.slaves),len(self.usedby),self.raid,pv,self.attr,self.quality,self.chunk]

    def add_volumes(self,name,guid='',provider=None,manual=True,size=0,auto=False):
        """
        The description of add_volumes comes here.
        @param name
        @param guid
        @param provider
        @param manual
        @param size
        @param auto
        @return
        """
        if self.volumes.has_key(name) : return None
        if manual:
            if not name or name=='#': name=getunique(self.volumes.keys(),'vol')
            tmplun=SanVolume(name,name,provider,size,auto)
            tmplun.pool=self.name
            tmplun.lvname=name
            tmplun.provider=self.provider
        else :
            tmplun=SanVolume(guid,name,provider)
        self.volumes.add(name,tmplun)
        return tmplun

    def set_provider(self,san,key,val='',test=0):
        """
        The description of set_provider comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        if self.glbl: return (1,'Cannot set provider value for Global pools')
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
        devobjs=[]; sign=''; first=True; tmppvd=None
        if len(val)>2 and val[0] in ['+','-'] :
            sign=val[0]
            val=val[1:]
        dl=val.split(';')
        for d in dl:
            (e,t,v)=volstr2obj(d,'drhb',self.provider,chklock=False, san=self.san_interface)
            if e : return (e,t)
            usedbyme=False
            for ext in v.usedby :
                if ext is self : usedbyme=True
            if v.locked and not usedbyme : return (1,'Device %s is locked and cannot be used to form a Pool' % v.name)
            if v.usedinluns:
                return (1, 'Device %s is already assigned to LUNs' % v.name)
            devobjs+=[v]
        if not test :
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
            if d.extent: tmp+=[obj2volstr(d.extent)]
        return (0,';'.join(tmp))

    def __used(self):
        """
        The description of __used comes here.
        @return
        """
        if self.glbl:
            tmp=0
            for sp in self.subpools():
                tmp += (sp.size - sp.free)
            return tmp
        else:
            return (self.size - self.free)

    totused = property(__used)

    def _getsizes(self):
        """
        The description of _getsizes comes here.
        @return
        """
        if self.glbl:
            sz=0
            for sp in self.subpools():
                sz += sp.size
        else:
            sz = self.size
        return (sz, self.free_space, self.totused)

    def _removeSlaves(self):
        """
        helper method for delete()
        """
        for s in self.slaves():
            self.slaves.delete(s)

    def delete(self,force=False):
        """
        The description of delete comes here.
        @param force
        @return
        """
        if self.state == ObjState.created or self.state == ObjState.absent:
            self._removeSlaves()
            return (0,'')

        if self.private and not force:
            return (1,'this is a private pool. use force to delete')

        if len(self.volumes) > 0:
            return (1,'cannot delete a Volume Group with Volumes, please delete the child Volumes first')

        if not self.glbl:
            self.state = ObjState.delete
            (e,o) = self.provider.del_vg(self)
        else:
            e=0
            o=''
            self.state = ObjState.delete
            for sp in self.subpools():
                sp.state = ObjState.delete
                (et,o) = sp.provider.del_vg(self)
                print 'del glbl pool:',sp.name,et,o
                self.subpools.delete(sp,True)
                e+=et
        if not e:    # TBD in case of one pvd failure, delete just those slave devices
            self._removeSlaves()
        return  (e,o)

    def update(self,flags=''):
        """
        The description of update comes here.
        @param flags
        @return
        """
        if self.state==ObjState.created and self.devices:
            # verify that the devices dont have partitions (cause LVM to fail)
            for d in self.devices :
                if (d.exttype=='physical' and d.partitions) or (d.exttype=='path' and d.parent.partitions):
                    return (1,'cant use devices with partitions to create a pool')
                if d.exttype=='physical' and len(d.paths)>1:
                    return (1,'cant use devices with multiple paths')

            self.manual=True
            if not self.glbl :
                tmppvd=None; first=True; devlist=[]
                for d in self.devices :
                    (e,pt)=ext2path(d,self.provider)
                    if e : return (e,'cant add Pool slave %s, ' % str(d))
                    if first :
                        if self.provider and not (pt.provider is self.provider) :
                            return (1,'devices must belong to the pool provider (%s)' % self.provider.name)
                        tmppvd=pt.provider
                        first=False
                    elif not pt.provider is tmppvd : return (1,'all devices must belong to the same provider (%s)' % tmppvd.name)
                    devlist+=[pt]

                if not self.provider : self.provider=tmppvd
                tmp=[d.name for d in devlist]
                print 'create vg %s on %s devs: %s' % (self.name,self.provider.name,','.join(tmp))
                (e,r)=self.provider.add_vg(self,devlist)
                print e,r
                if e : return (e,r)
            else :
                pvddev={}
                for d in self.devices :
                    (e,pt)=ext2path(d)
                    pn=pt.provider.name
                    if pvddev.has_key(pn) : pvddev[pn]+=[pt]
                    else : pvddev[pn]=[pt]
                for pname in pvddev.keys():
                    pvd=self.san_interface.providers[pname]
                    if not self.subpools.has_key(pname):
                        sp=self.subpools.add(pname,VolGrpSubpool(pname,pvd))
                    tmp=[d.name for d in pvddev[pname]]
                    print 'create vg %s on %s devs: %s' % (self.name,pname,','.join(tmp))
                    (e,r)=pvd.add_vg(self,pvddev[pname])
                    print e,r
                    if e : return (e,r)
            for d in self.devices : d.pool=self.name
            self.devices=[]
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
        tmp='%s%s %-20s %-8s Volumes:%d  Size:%s  Used:%s  Free:%s  %d %s' % \
           (ident,l,self.name,self.state,len(self.slaves),printsz(self.size),printsz(self.totused),printsz(self.free_space),self.chunk,self.attr)
        if level>0:
            tmp+='\n'+ident+'   Physical Volumes:'
            for p in self.slaves()  : tmp+='\n'+p.show(mode,level-1,ident+'    ')
            tmp+='\n'+ident+'   Logical Volumes:'
            for p in self.volumes()  : tmp+='\n'+p.show(mode,level-1,ident+'    ')
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
        if self.auto or self.private or 'VolGroup00' in self.name:
            return []
##        if not self.manual : canadd=False
        return SanBase.export(self,san,path,canadd)
