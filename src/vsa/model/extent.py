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
from vsa.model.vsa_collections.ref_dict import RefDict
from vsa.model.target import TargetLun
from vsa.infra.params import IoSchedType, ObjState, paramopts, RaidLevel
from vsa.infra.infra import printsz, txt2size, iif
from vsa.infra import logger


class Extent(SanBase):
    set_params=['reqstate','readahead','vparams']
    #show_columns=[' ','Name','Type','Size','devfile']

    def __init__(self,guid='',name='',desc='Extent'):
        """
        The description of __init__ comes here.
        @param guid
        @param name
        @param desc
        @return
        """
        SanBase.__init__(self,name,desc)
        self.guid=guid
        self.exttype='base'   #  physical / partition / virtual / memory / snapshot / diskgroup
        self._locked=False
        self.updateflag=0
        self.cacheresource=False   # Extent used as a cache
        self.idx=0
        self.auto=False        # Auto Generated, by an upper object
        self.size=0        # size in MB
        self.used=0           # used size in MB
        self.pool=''          # belong to storage pool name
        self.access='w'       # access r - read only, w - Read and Write
        self.basedon=[]       # based on extents, list of parent extents (e.g. a volume based on a partition based on a disk)
        self.bootable = 0     # is it used as a boot disk
        self.primordial=0     # primary extent, based on physical HW (e.g. not a logical volume)
        self.usedby = []      # pointers to objects using this extent
        self.usedinluns=[]    # target luns using this volume
        self.inluns=RefDict(TargetLun,self,'inluns',desc='Used In Targets/LUNs',icon='hard_disk.png',call=lambda self:[v for v in self.usedinluns])
        self.exclusive=True   # only one user can access that LUN (vs. shared)
        self.devfile=''       # block device name in target/router e.g. sdb, TBD need to relate to provider
        self.blkfile=''       # block device name in target/router as its in /sys/block
        self.mount=''
        self.vparams={}
        self.cachedict={}
        self.cachepresent=False

        self.iscached=False   # is this Extent cached
        self.cachedev=''      # Cache device assosiated with this extent
        self.cachesize=0      # Cache size in MB, zero for entire device
        self.iosched=IoSchedType.default       # IO Scheduler (CPQ / Noop / ..)
        self.iodepth=''          # IO Scheduler depths
        self.readahead=0      # number of read ahead blocks
        self.private=False    # private extent. i.e. user cannot add it to lun.

    def __getlocked(self):
        """
        The description of __getlocked comes here.
        @return
        """
        return self._locked

    def __setlocked(self, value):
        """
        The description of __setlocked comes here.
        @param value
        @return
        """
        if value: self._locked=value
        else: self.unlock()

    locked = property(__getlocked,__setlocked)

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.locked*'L',self.name,self.exttype,printsz(self.size),self.devfile]

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
        if new == ObjState.absent:
            self.cachepresent=False

    def set_cachesize(self,san,key,val='',test=0):
        """
        The description of set_cachesize comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        (e,v)=txt2size(val,self.size)
        if e : return (e,v)
        if self.cachesize==v : return (0,'')
        if self.locked : return (1,'cannot change cache on a Locked storage object')
        if len(self.usedinluns) : return (1,'cannot change cache on a storage object which is assigned to a LUN, remove the Lun first')
        if self.cachesize>0 and v<>0 : return(1,'cannot resize cache, remove cache first (set to 0)')
        if not test : self.cachesize=v
        return (0,'')

    def set_vparams(self,san,key,val='',test=0):
        """
        The description of set_vparams comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        return san.robots.set_strdict(self,key,val,test,paramopts)

    def __repr__(self):
        """
        The description of __repr__ comes here.
        @return
        """
        g=''
        if self.guid and self.guid <> self.name:
            g = '(%s)' % self.guid
        return '%s:%s' % (self.exttype,self.name) + g

    def __str__(self):
        """
        The description of __str__ comes here.
        @return
        """
        return self.__repr__()

    def show(self,mode=0,level=0,ident=''):
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        return '%sType:%s Name:%s Size:%s' % (ident,self.exttype,self.name,printsz(self.size))

    def unlock(self):
        """
        Try to unlock the extent
        """
        self._cleanlock()

    def _cleanlock(self):
        """
        helper method for unlock()
        check if all childs are unlocked
        """
        if self._locked==False: return
        lock=False
        if self.exttype=='physical':
            for p in self.usedby:
                if p.locked:
                    lock=True
                    break
        self._locked=lock
        # to try to unlock parents
        if self.exttype=='partition':
            for p in self.basedon:
                p.unlock()


class PoolItem(SanBase): # TBD
    #show_columns=['Slot/Role','Provider','DataState','ConnState','Size','dev','Extent']
    set_params=['promote','change','device']
    #ui_buttons=[del_btn,promote_btn,reinit_btn]

    def __init__(self,name,provider=None):
        """
        The description of __init__ comes here.
        @param name
        @param provider
        @return
        """
        SanBase.__init__(self,name,'Storage Pool item')
        self.slot=''
        self.provider=provider
        self.extent=None
        self.datastate=''
        self.connstate=''
        self.candidate=False
        self.dataerrors=0
        self.size=0
        self.spare=False
        self.role=''

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        if self.extent : sz=self.extent.size
        else : sz=0
        if self.provider : pvd=self.provider.name
        else : pvd=''
        return [iif(self.parent.raid==RaidLevel.dr,self.role,self.slot),pvd,self.datastate,self.connstate,printsz(sz),self.name,str(self.extent)]

    def promote(self,a='',b='',checkluns=True):
        """
        The description of promote comes here.
        @param a
        @param b
        @param checkluns
        @return
        """
        if self.parent.raid == RaidLevel.dr:
            if checkluns and len(self.parent.usedinluns):
                return (1,'cannot change master item used in Target LUNs, use target migrate command')
            if self.provider.state == ObjState.absent:
                return (1,'cannot promote DR on provider %s, provider unreachable/absent' % self.provider.name)
            for s in self.parent.slaves():
                if s is not self and s.state != ObjState.absent:
                    (e,o) = s.provider.update_drbd(self.parent.name,"secondary")
                    if e:
                        logger.eventlog.error('Cannot demote DR slave %s on %s, Err: %s' % (self.parent.name,s.provider.name,str(o)))
            (e,o) = self.provider.promote_drbd(self.parent.name)
            if e:
                return (e,o)
        return (0,'')

    def change(self,a='',b=''):
        """
        The description of change comes here.
        @param a
        @param b
        @return
        """
        if self.parent.raid==RaidLevel.dr:
            (e,o)=self.provider.update_drbd(self.parent.name,a)
            if e : return (e,o)
        return (0,'')

    def device(self,new=''):
        """
        The description of device comes here.
        @param new
        @return
        """
        return self.parent.replace_device(self,new)

    def show(self,mode=0,level=0,ident=''):
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        o='off'; ex=''
        if self.state==ObjState.running : o='on '
        if self.extent : ex=' Volume: %s Size:%s' % (self.extent.guid,printsz(self.extent.size))
        tmp='%s%-5s%s %-12s %-12s' % (ident,self.slot,o,self.datastate,self.connstate) + ex
        if level>0 and self.extent:
            tmp+='\n'+self.extent.show(mode,level-1,ident+'    ')
        return tmp
