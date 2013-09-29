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


from vsa.model import volstr2obj, obj2volstr, ext2path
from vsa.model.san_base import SanBase
from vsa.client.gui.htmbtns import add_btn, del_btn
from vsa.infra.params import Transport, ObjState
from vsa.infra.infra import printsz
from vsa.infra import logger
from vsa.model.san_target import SanTarget


class vDisk(SanBase):
    set_params=['volume','pool','size','priority','avgload','paths','transport']
    newonly_fields=['volume','pool','size','transport']
    #show_columns=['Name','Pool','Req Size','Volume','Priority','AvgLoad','Paths','Target']
    #ui_buttons=[add_btn,del_btn]

    def __init__(self,name):
        """
        The description of __init__ comes here.
        @param name
        @return
        """
        SanBase.__init__(self,name,'Virtual Disk')
        self.volume=None
##        self.devstr=''
        self.pool=None
        self.size=0
        self.priority=0
        self.avgload=0
        self.paths=2
        self.transport=Transport.iscsi
        self.target=None

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        if self.pool : pl=self.pool.name
        else : pl=''
        return [self.name,pl,printsz(self.size),str(self.volume),self.priority,self.avgload,self.paths,str(self.target)]


    def set_volume(self,san,key,val='',test=0):
        """
        The description of set_volume comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        if self.pool : return (1,'already assigned this vDisk to a pool (%s)' % str(self.pool))
        (e,t,v)=volstr2obj(val,'drbhv', san=self.san_interface)
        if e : return (e,t)
        if not test : self.volume=v
        return (0,'')

    def get_volume(self,san,key):
        """
        The description of get_volume comes here.
        @param san
        @param key
        @return
        """
        return (0,obj2volstr(self.volume,''))


    def set_pool(self,san,key,val='',test=0):
        """
        The description of set_pool comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        if self.volume and san.runmode : return (1,'already assigned this vDisk to a volume (%s)' % str(self.volume))
        if not san.pools.has_key(val): return (1,'pool named %s doesnt exist')
        if not test : self.pool=san.pools[val]
        return (0,'')

    def get_pool(self,san,key):
        """
        The description of get_pool comes here.
        @param san
        @param key
        @return
        """
        if self.pool : return (0,self.pool.name)
        return (0,'')

    def update(self,flags=''):
        """
        The description of update comes here.
        @param flags
        @return
        """
        if self.state==ObjState.created:
            if not self.volume and self.pool and self.size>0 :
                vol=self.pool.add_volumes('vdisk.'+self.parent.name+'.'+self.name,size=self.size,auto=True)
                if vol : (e,r)=vol.update()
                else : logger.eventlog.debug('vDisk new volume is null')
                self.volume=vol
            if not self.volume :
                return (1,'User must specify an existing volume or a pool and size')
            (e,pt)=ext2path(self.volume)
            if e :
                return (e,'cant add vDisk with volume %s, ' % str(self.volume))
            name='iqn.vsa.vdisk.%s.%s' % (self.parent.name,self.name)
            if not self.san_interface.targets.has_key(name) :
                logger.eventlog.debug('adding vDisk target:'+name)
                itg=self.san_interface.targets.add(name,SanTarget(name,pt.provider))
                itg.transport=self.transport
            else :
                itg=self.san_interface.targets[name]
                if itg.device and not (itg.device is pt.provider):
                    return (1,'vDisk target already exists with a different provider (%s)' % itg.device.name)
            itg.server=self.parent
            itg.auto=True
            itg.update()
            self.parent.targets[name]=itg
            self.target=itg
            lun=itg.add_luns('#',pt)
            logger.eventlog.debug('added lun')
            if lun :
                lun.update()
                self.change_state(ObjState.running)
            else : logger.eventlog.debug('vDisk Lun is null')
        return (0,'')

    def delete(self,force=False):
        """
        The description of delete comes here.
        @param force
        @return
        """
        logger.eventlog.info('Delete vDisk: %s %s' % (self.name,str(force)))
        if self.state<>ObjState.created :
            # TBD - self.provider.fcports[self.fchost].assignbw-=self.avgload
            k = self.target.name
            del self.parent.targets[k]
            (e,txt)=self.san_interface.targets.delete(self.target,True)
            return (e,txt)
        return (0,'')

    def export(self,san,path,canadd=True):
        """
        The description of export comes here.
        @param san
        @param path
        @param canadd
        @return
        """
        exclude=[]
        if self.volume : exclude=['pool','size']
        return SanBase.export(self,san,path,canadd,exclude)
