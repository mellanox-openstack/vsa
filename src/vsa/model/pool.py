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
from vsa.infra.infra import printsz

class VolGrpItem(SanBase):
    #show_columns=['Size','Free','PE','Alloc','Extent']
    #ui_buttons=[add_btn]

    def __init__(self,name,provider=None):
        """
        The description of __init__ comes here.
        @param name
        @param provider
        @return
        """
        SanBase.__init__(self,name,'Volume Group item')
        self.slot=''
        self.provider=provider
        self.extent=None
        self.attr=''
        self.free=0
        self.size=0
        self.pe=0
        self.alloc=0

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [printsz(self.size),printsz(self.free),self.pe,self.alloc,str(self.extent)]

    def show(self,mode=0,level=0,ident=''):
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        ex=''
        if self.extent:
            ex=' Volume: %s ' % (self.extent.guid)
        tmp = '%s %-8s Size: %s  Free: %s  PE: %s alloc: %s' % (ident,str(self.state),printsz(self.size),printsz(self.free),self.pe,self.alloc) + ex
        if level > 0 and self.extent:
            tmp += '\n' + self.extent.show(mode,level-1,ident+'    ')
        return tmp


class VolGrpSubpool(SanBase):
    #show_columns=['Provider','Size','Used','Free','attr']
    def __init__(self,name='',provider=None):
        """
        The description of __init__ comes here.
        @param name
        @param provider
        @return
        """
        SanBase.__init__(self,name,'Volume Group Subpool')
        self.provider=provider
        self.chunk=0
        self.size=0
        self.free=0
        self.attr=''
        self.guid=''
        self._flush()

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [getattr(self.provider,'name',''),printsz(self.size),printsz(self.size-self.free),printsz(self.free),self.attr]

