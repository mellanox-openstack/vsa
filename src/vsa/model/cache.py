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


from vsa.model.san_base import  SanBase
from vsa.infra.params import CachePolicy
from vsa.model.vsa_collections import VSACollection
import os

class CacheInst(SanBase):
    def __init__(self,name,resource,ext,bsize=0,csize=0):
        """
        The description of __init__ comes here.
        @param name
        @param resource
        @param ext
        @param bsize
        @param csize
        @return
        """
        SanBase.__init__(self,name,'Cache Device')
        self.name=name
        self.resource=resource
        self.ext=ext
        self.blksize=bsize   # cache block size, 0 for default
        self.csize=csize     # total cache size, 0 for default

class CacheRes(SanBase):
    def __init__(self,extent):
        """
        The description of __init__ comes here.
        @param extent
        @return
        """
        SanBase.__init__(self,extent.name,'Cache Resource')
        self.extent=extent
        self.used=0
        self.useall=True
        self.usedby={}

class CacheMngr(SanBase):
    child_obj=['resources','cachedevs']
    add_commands=[]
    set_params=['reclaim_policy','write_merge','dirty_thresh','sync','stopsync']
    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        SanBase.__init__(self,'Cache','Cache Class')
        self.fullpath='/cache'
        self.reclaim_policy=CachePolicy.fifo
        self.write_merge=True
        self.dirty_thresh=0
        self.resources=VSACollection(CacheRes,self,'resources')
        self.cachedevs=VSACollection(CacheInst,self,'cachedevs')

    def add_res(self,extent):
        """
        The description of add_res comes here.
        @param extent
        @return
        """
        if extent.name not in self.resources.keys():
            self.resources[extent.name]=CacheRes(extent)
            extent.locked=True
            if self not in extent.usedby : extent.usedby+=[self]

    def del_res(self,extent):
        """
        The description of del_res comes here.
        @param extent
        @return
        """
        if extent.name in self.resources.keys():
            extent.locked=False
            del self.resources[extent.name]

    def add_cache(self,ext,bsize=0,csize=0,resource=None):
        """
        The description of add_cache comes here.
        @param ext
        @param bsize
        @param csize
        @param resource
        @return
        """
        if ext.iscached:
            print 'already cached'
            return
        r=None
        for i in self.resources.values():
            if len(i.usedby)==0 :
                r=i
                break
        if not r :
            print 'no available cache resources'
            return

        r.usedby[ext.name]=ext
        ext.iscached=True
        tmp=''
        if bsize : tmp+=' -s %dm' % csize
        if bsize : tmp+=' -b %dk' % bsize
        name='cache_'+r.extent.devfile+'_'+ext.devfile
        self.cachedevs[name]=CacheInst(name,r,ext,bsize,csize)
        ext.cachedev=name
        print 'flashcache_create%s %s /dev/%s /dev/%s' % (tmp,name,r.extent.devfile,ext.devfile)

    def del_cache(self,name):
        """
        The description of del_cache comes here.
        @param name
        @return
        """
        if not self.cachedevs.has_key(name) : return
        cd=self.cachedevs[name]
        cd.ext.iscached=False
        cd.ext.cachedev=''
        cd.resource.usedby={}
        del cd
        print 'dmsetup remove '+name

    def _sysctl(self,s):
        """
        The description of _sysctl comes here.
        @param s
        @return
        """
        try:
            return os.popen('sysctl -w dev.flashcache.'+s,'r').read()
        except:
            return ''
    def zero_stats(self,a='',b=''):
        """
        The description of zero_stats comes here.
        @param a
        @param b
        @return
        """
        self._sysctl('zero_stats')

    def sync(self,a='',b=''):
        """
        The description of sync comes here.
        @param a
        @param b
        @return
        """
        self._sysctl('do_sync')

    def stopsync(self,a='',b=''):
        """
        The description of stopsync comes here.
        @param a
        @param b
        @return
        """
        self._sysctl('stop_sync')

    def update(self,flags=''):
        """
        The description of update comes here.
        @param flags
        @return
        """
        rp=0; wm=1;
        if self.reclaim_policy<>CachePolicy.fifo: rp=1
        if not self.write_merge : wm=0
        self._sysctl('reclaim_policy='+str(rp))
        self._sysctl('write_merge='+str(wm))
        if self.dirty_thresh : self._sysctl('dirty_thresh_pct='+str(self.dirty_thresh))
        return (0,'')

