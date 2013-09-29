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


from IPy import IP
from vsa.model.san_base import SanBase
from vsa.client.gui.htmbtns import extmon_btn


class Netif(SanBase):
    set_params = ['ip','mask','bcast','dhcp','mtu','mng','data','group']
    #show_columns = ['Name','IP','Mask','Grp','Speed','dhcp','data','mng','mtu','mac']
    #ui_buttons = [extmon_btn]

    def __init__(self,name,link='Ethernet',mac='',ip='0.0.0.0',mask='0.0.0.0',bcast='',vlan=0,dhcp=False):
        """
        The description of __init__ comes here.
        @param name
        @param link
        @param mac
        @param ip
        @param mask
        @param bcast
        @param vlan
        @param dhcp
        @return
        """
        SanBase.__init__(self,name,'Net interface')
        self.link=link
        self.mac=mac
        self.ip=IP(ip)
        self.mask=IP(mask)
        self.bcast=bcast
        self.vlan=vlan
        self.dhcp=dhcp
        self.mtu=0
        self.group=0
        self.mng=True
        self.data=True
        self.speed=0
        self.parif=''
        self.isvirtual=False
        self._flush()
        self.icon=""

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.name,self.ip,self.mask,self.group,self.speed,self.dhcp,self.data,self.mng,self.mtu,self.mac]

    def subnet(self):
        """
        The description of subnet comes here.
        @return
        """
        return IP(str(self.ip)+'/'+str(self.mask),make_net=True)

    def export(self,san,path,canadd=True):
        """
        The description of export comes here.
        @param san
        @param path
        @param canadd
        @return
        """
        exclude=[]
        if san.general.noifconfig :
            exclude=['ip','mask','bcast','dhcp','mtu']
            return SanBase.export(self,san,path,canadd,exclude)
        if self.dhcp : exclude=['ip','mask']
        return SanBase.export(self,san,path,canadd,exclude)

    def update(self,flags=''):
        """
        The description of update comes here.
        @param flags
        @return
        """
        chg=0
        for i in self._updatedattr :
            if i in ['ip','dhcp','mask','bcast'] : chg=1
        if not chg : return (0,'')
        (e,txt)=self.parent.set_if(self.name,self.dhcp,str(self.ip),str(self.mask),str(self.bcast),self.vlan,self.mtu)
        self.parent.get_ifs()
##        self._flush()
        return (e,txt)

    def show(self,mode=0,level=0,ident='') :
        """
        The description of show comes here.
        @param mode
        @param level
        @param ident
        @return
        """
        if self.speed<1000 : spd=str(self.speed)
        else : spd=str(self.speed/1000)+'G'
        return "%s%-9s %-8s %-3s IP: %s/%s %4s Mac:%-18s" %  (ident,self.name,self.state,spd,self.ip,self.mask,'dhcp'*self.dhcp,self.mac)

