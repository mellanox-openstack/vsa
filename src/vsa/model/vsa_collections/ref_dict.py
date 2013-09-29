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


from vsa.infra.infra import iif, val2str
from vsa.events.VSAEvents import SevEnum
from vsa.client.component_handler import get_columns



class RefDict(dict):

    def __init__(self, typ=object, owner = None,path='',desc='',icon='',call=None,cols=[],table=None):
        """
        The description of __init__ comes here.
        @param typ
        @param owner
        @param path
        @param desc
        @param icon
        @param call
        @param cols
        @param table
        @return
        """
        self.cclass=typ
        self.description=iif(desc,desc,path.capitalize())
        self.fullpath=owner.fullpath+'/'+path
        self.icon=icon
        self.call=call
        self.cols=cols
        self.table=table
        self.owner=owner

    def __call__(self):
        """
        The description of __call__ comes here.
        @return
        """
        if self.call:
            return self.call(self.owner)
        elif self.table:
            return self.table(self.owner)
        else:
            return self.values()

    def get_object_type(self):
        """
        return string with object type name
        """
        return self.__class__.__name__

    def clr(self):
        """
        The description of clr comes here.
        @return
        """
        for k in self.keys():
            del self[k]

    def print_tbl(self,ident='',width=120,idx='',lvl=0,sep=' ',all=False):
        """
        The description of print_tbl comes here.
        @param ident
        @param width
        @param idx
        @param lvl
        @param sep
        @param all
        @return
        """
        if self.cols : h=self.cols
        else : h = ['State'] + get_columns(self)
        rng=range(len(h))
        csize=[0]*len(h)
        for i in rng : csize[i]=len(h[i])
        tbl=[h]
        if self.table :
            for row in self.table(self.owner) :
                r=[val2str(x) for x in row]
                tbl+=[r]
                for i in rng :
                    if len(r[i])>csize[i] : csize[i]=len(r[i])
        else :
            for o in self.__call__() :
                a='!'*(o.alarmstate<>SevEnum.none)
                r=[str(o.state)+a.ljust(1)]+[val2str(x) for x in self.cclass.ui_getrow(o)]
                tbl+=[r]
                for i in rng :
                    if len(r[i])>csize[i] : csize[i]=len(r[i])
        out=[]; x=0
        for l in tbl:
            txt=''
            for i in rng :
                if len(ident+txt)<width : txt+=l[i].center(csize[i])+sep
            out+=[ident+txt]
            x+=1
        return '\n'.join(out)

    def export(self,san,path,canadd=True):
        """
        The description of export comes here.
        @param san
        @param path
        @param canadd
        @return
        """
        return []

