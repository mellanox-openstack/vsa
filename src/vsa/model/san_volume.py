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
from vsa.infra.infra import printsz, txt2size, tstint
from vsa.infra.params import ObjState

class SanVolume(Extent):
    child_obj=['inluns']
    set_params=Extent.set_params+['size','dr','stripes','stripesize']
    newonly_fields=['readahead','stripes','stripesize']
    #show_columns=[' ','Name','Size','Mount','InLUNs','Snaps']
    #ui_buttons=[add_btn,del_btn,mapto_btn,addtotgt_btn,snap_btn,extmon_btn]

    def __init__(self,guid='',name='',provider=None,size=0,auto=False):
        """
        The description of __init__ comes here.
        @param guid
        @param name
        @param provider
        @param size
        @param auto
        @return
        """
        Extent.__init__(self,guid,name,'Logical Volume')
        self.exttype='virtual'
        self.provider=provider
        self.lvname=''
        self.capabilities=[]  # enabled cap: mirror/replica/backup/wcache/cdp/..
        self.snapgroup=None   # snapshot TBD
        self.primordial=0     # primary extent, based on physical HW (e.g. not a logical volume)
        self.creator=None
        self.mount=''
        self.size=size
        self.auto=auto
        self.dr=False
        self.manual=False
        self.stripes=0        # number of stripes to scatter
        self.stripesize=8    # default stripe size 8kb

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.locked*'L',self.name,printsz(self.size),self.mount,len(self.usedinluns),'0']

    def set_size(self,san,key,val='',test=0):
        """
        The description of set_size comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        if self.parent and self.parent.private and san.runmode:
            return (1, 'cant create volumes on private pool %s' % self.parent.name)
        sign=''
        # allow sign only in running state
        if self.state == ObjState.running and len(val) > 1 and val[0] in ['+','-']:
            sign=val[0]
            val=val[1:]
        (e,v)=txt2size(val)
        if e:
            return (e,'volume size error,'+v)
        if val==v:
            return (0,'')
        if self.size == v and not sign:
            return (0,'')
        if self.state == ObjState.created:
            if v > self.parent.free_space:
                return (1,'Volume size is greater than volume group free space (%s)' % printsz(self.parent.free_space))
            if not test : self.size=v
        elif self.state==ObjState.running:
            if test : return (0, '')
            if sign=='+': v=self.size+v
            elif sign=='-': v=self.size-v
            if v > self.size : # extend
                if v > self.parent.free_space + self.size:
                    return (1,'New volume size is greater than volume group free space (%s) + current size (%s)' % ( printsz(self.parent.free_space), printsz(self.size) ))
                return self._extend(v)
            elif v < self.size : # reduce
                if v < 1:
                    return (1,'New volume size cannot be lower than 1M')
                return self._reduce(v)
        else:
            return (1,'cannot change size at current state')
        return (0,'')

    def _extend(self, size):
        """
        The description of _extend comes here.
        @param size
        @return
        """
        e,r = self.provider.extend_volume(self, size)
        if e:
            return e,r
        self._update_in_luns()
        return (0,'')

    def _reduce(self, size):
        """
        The description of _reduce comes here.
        @param size
        @return
        """
        e,r = self.provider.reduce_volume(self, size)
        if e:
            return e,r
        self._update_in_luns()
        return (0,'')

    def _update_in_luns(self):
        """
        The description of _update_in_luns comes here.
        @return
        """
        for lun in self.usedinluns:
            lun.update_devfile()

    def set_stripes(self,san,key,val='',test=0):
        """
        The description of set_stripes comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        v = tstint(val)
        if v < 0 :
            return (1,'Invalid number of stripes')
        if v > len(self.parent.slaves):
            return (1, 'Number of stripes must not exceed number of physical volumes')
        if not test :
            self.stripes = v
        return (0,'')

    def delete(self, force=False):
        """
        The description of delete comes here.
        @param force
        @return
        """
        if self.state == ObjState.created:
            return (0,'')
        if self.parent.private and not force:
            return (1,'this is a private volume. use force to delete')
        if self.auto and not force:
            return (1,'Cannot Delete Auto Generated Volumes')
        self.state = ObjState.delete
        (e,o) = self.provider.del_volume(self)
        if e:
            return (e,o)
        if self in self.parent.usedby:
            self.parent.usedby.remove(self)
        return (e,o)

    def update(self,flags=''):
        """
        The description of update comes here.
        @param flags
        @return
        """
        if self.state==ObjState.created and self.size:
            self.manual=True
            (e,pvds)=self.parent.find_space(self.size,self.dr)
            if e : return (e,pvds)
        # TBD add DRBD in case of .dr
            for p in pvds:
                (e,r)=p.add_volume(self)
                print e,r
                if e: return (e,r)
#           self._flush()
        return (0,'')

    def show(self,mode=0,level=0,ident=''):
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        tmp = '%sv%-3d  %-30s  %6d %10s %-10s' % \
          (ident,self.idx,self.name,len(self.basedon),printsz(self.size),self.exttype)

        if level>0:
            tmp+='\n'+ident+'  Based on:'
            for p in self.basedon : tmp+='\n'+p.show(mode,level-1,ident+'   ')
            tmp+='\n'
        return tmp

