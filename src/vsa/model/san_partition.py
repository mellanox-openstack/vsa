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
from vsa.model.vsa_collections.ref_dict import RefDict
from vsa.infra.infra import printsz

class SanPartition(Extent):
    child_obj=['usedin']
    #show_columns=[' ','Idx','Name','Device','Start','Size','Type','Mount','inLuns']
    def __init__(self,guid='',idx=0,size=0,start=0,ptype='',mount=''):
        """
        The description of __init__ comes here.
        @param guid
        @param idx
        @param size
        @param start
        @param ptype
        @param mount
        @return
        """
        super(SanPartition, self).__init__(guid=guid,name=`idx`,desc='Partition')
        self.exttype='partition'
        self.idx=idx
        self.provider=None
        self.size=size
        self.start=start
        self.ptype=ptype
        self.mount=mount
        self.usedin=RefDict(Extent,self,'usedin',desc='Owned By Storage Extents',icon='hard_disk.png',call=lambda self:[v for v in self.usedby])

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.locked*'L',self.idx,self.guid,self.devfile,self.start,printsz(self.size),self.ptype,self.mount,len(self.usedinluns)]

    def show(self,mode=0,level=0,ident=''):
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        par=self.basedon[0].name
        if self.locked : l='L'
        else : l=' '
        tmp = '%s%s %s %s Start: %10d  Size: %10s  Type: %s  Mount: %s' % (ident,l,self.guid,self.devfile,self.start,printsz(self.size),self.ptype,self.mount)
        if level>0:
            tmp+='\n'+ident+'  Used in:'
            for p in self.usedby : tmp+='\n'+p.show(mode,level-1,ident+'   ')
            tmp+='\n'
        return tmp

