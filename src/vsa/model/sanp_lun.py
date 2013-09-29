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


import extent
from vsa.client.gui.htmbtns import addtopool_btn, addtoraid_btn, addtotgt_btn,\
    extmon_btn, mapto_btn
from vsa.infra.params import RaidLevel, ObjState, IoSchedType, ReqState, CACHESEP,\
    CACHEPFX
from vsa.model.vsa_collections import VSACollection, RefDict
from vsa.model import san
from vsa.model.san_partition import SanPartition
from vsa.infra.infra import printsz
from vsa.model import ext2path, obj2volstr
from vsa.infra import logger
from vsa.model.san_raid_group import SanRaidGrp


class Sanplun(extent.Extent):
    child_obj=['paths','partitions','usedin','inluns']
    set_params=['reqstate','readahead','direct','iosched','vparams','cachesize']
    #show_columns=[' ','Idx','Name','Size','Cache','Vendor','Model','paths','prt','in LUNs']
    #ui_buttons=[mapto_btn,addtotgt_btn,addtoraid_btn,addtopool_btn,extmon_btn]

    def __init__(self,guid='',name=''):
        """
        The description of __init__ comes here.
        @param guid
        @param name
        @return
        """
        extent.Extent.__init__(self,guid,name,'Physical LUN/Disk')
        self.exttype='physical'
        self.alias=''
        self.alwaysadd=True
        self.direct=True
        self.serial=''        # SCSI Serial ID
        self.model=''         # SCSI Model
        self.vendor=''        # SCSI Vendor
        self.revision=''      # SCSI revision
        self.raid=RaidLevel.none   # underline raid '0' '1' '5' '6' '10'
        self.sectorsize=512
        self.paths=VSACollection(san.SanPath,self,'paths',desc='Paths To Disk',icon='link_g.png') # list of paths leading to this physical disk (local or remote), key = dev/hbtl
        self.partitions=VSACollection(SanPartition,self,'partitions',icon='vm_g.png') # list of paths leading to this physical disk (local or remote), key = dev/hbtl
        self.usedin=RefDict(extent.Extent,self,'usedin',desc='Owned by Storage Extents',icon='hard_disk.png',call=lambda self:[v for v in self.usedby if v.exttype<>'partition'])
        self.assigned=[]      # list of chunks assigned from this disk
        self.primordial=1     # primary extent, based on physical HW (e.g. not a logical volume)
        self.cachepvds=[]     # list of provider names which have a matching cache logical volume (found in discovery, process extents)
        self.cachedrdev=None  # points to cache DRBD device
        self._flush()

    def ui_getrow(self):
        """
        The description of ui_getrow comes here.
        @return
        """
        return [self.locked*'L',self.idx,self.guid,printsz(self.size),
            printsz(self.cachesize),self.vendor,self.model,
            len(self.paths),len(self.partitions),len(self.usedinluns)
            ]

    def __used(self):
        """
        The description of __used comes here.
        @return
        """
        tot=0
        assign={}
        for c in self.assigned :
            if not assign.has_key(c.start) :
                assign[c.start]=c.end
                tot+=c.end-c.start+1
        return tot

    def delete(self,force=False):
        """
        The description of delete comes here.
        @param force
        @return
        """
        if self.state == ObjState.created or self.state == ObjState.absent:
            return (0,'')
        else:
            return (1,'cannot delete a live disk (only absent or user created ones)')

    def _get_2_pvds_paths(self):
        """
        The description of _get_2_pvds_paths comes here.
        @return
        """
        # find 2 providers and paths to be used for cache
        (e1,path1)=ext2path(self)
        (e2,path2)=ext2path(self,exclude=[path1.provider])
        #for pt in self.paths():
        #    if pt.state==ObjState.running and pt.reqstate==ReqState.enabled and not (pt.provider is path1.provider) :
        #        path2=pt; break;
        print 'cache paths: ',str(path1),str(path2)
        if e1 or e2:
            return (1, 'valid paths not found','')
        return (0,path1,path2)

    def _update_params(self):
        """
        The description of _update_params comes here.
        @return
        """
        _load = not self.san_interface.runmode
        params={}
        if ('iosched' in self._updatedattr or _load) and self.iosched<>IoSchedType.default:
            params['iosched']=str(self.iosched)
        if ('readahead' in self._updatedattr or _load) and self.readahead :
            params['readahead']=self.readahead
        if params:
            for pt in self.paths():
                pt.provider.set_dev_params(pt,params)

    def _get_pvds(self):
        """
        The description of _get_pvds comes here.
        @return
        """
        pvds = []
        for path in self.paths():
            if path.reqstate == ReqState.enabled and path.provider.name not in pvds:
                pvds += [path.provider.name]
        return pvds

    def _update_cachesize(self):
        """
        The description of _update_cachesize comes here.
        @return
        """
        san_res = self.san_interface
        _load = not self.san_interface.runmode
        if self.cachesize > 0:
            pvds = self._get_pvds()
            if len(pvds) < 1:
                # not suppposed to get here
                return (1,'Error no valid provider/path was found when setting cache')
            logger.eventlog.debug('in update cache for %s , cachedrdev: %s' % (str(self),str(self.cachedrdev)))
            # check if this is a single path case or replicated cache (multipath)
            if len(pvds) == 1 and len(self.cachepvds) < 2 and not self.cachedrdev:
                (e,pt) = ext2path(self,san_res.providers[pvds[0]])
                if e:
                    return (e,'Error updating cache, '+pt)
                (e,r) = san_res.providers[pvds[0]].add_cache(pt,self.cachesize)
                if e:
                    return (e,r)
            else:
                #
                # more than 1 path
                #

                # one path with cacheon and is running return ok
                for pt in self.paths():
                    if pt.cacheon:
                        if pt.state == ObjState.running:
                            return (0,'Cache is ok')
                        logger.eventlog.warning('cache for %s is ON but path is not running !' % str(self))

                # no running path with cache on
                self.cachepresent=False

                #
                cvolname=obj2volstr(self)
                cvolname=cvolname.replace(':',CACHESEP) # replace ':' with a legal volume char
                drname=CACHEPFX+cvolname
                cache_loadonly=False
                #

                # self.cachedrdev ?
                if self.san_interface.raids.has_key(drname):
                    # found drbd dev for cache (fail-over or load??):
                    # del tgt (old), remove cache (old), promote (new),
                    # cache load (new), add targets (new)
                    logger.eventlog.warning('Cache for %s is not on, while DR device is detected during update' % str(self))
                    drdev = self.san_interface.raids[drname]
                    if not drdev:
                        logger.eventlog.error('cant update cache dr for %s , drdev not found' % (str(self)))
                        return (1,'cant update Cache dr')
                    if not drdev.provider:
                        drdev.promote_one(checkluns=False)
                    if not drdev.provider:
                        logger.eventlog.error('cant update cache dr for %s , drdev provider not detected' % (str(self)))
                        return (1,'cant update Cache dr')
                    # debug
                    #logger.eventlog.debug("cachepresent: %s" % str(self.cachepresent))
                    #for p in self.paths():
                    #    if p.provider==drdev.provider:
                    #        logger.eventlog.debug("p: %s" % str(p))
                    #        logger.eventlog.debug("state: %s" % str(p.state))
                    #        logger.eventlog.debug("cacheon: %s" % str(p.cacheon))
                    # end debug
                    e,prim = ext2path(self,drdev.provider)
                    if e:
                        logger.eventlog.error('valid path not found for %s on %s in update' % (str(self),str(drdev.provider)))
                        return (1,'valid path not found')
                    #logger.eventlog.debug("prim: %s" % str(prim))
                    cache_loadonly=True
                else:
                    if len(self.cachepvds)==1 or len(self.cachepvds)>2:
                        # has only 1 cache LV (load, absent?) ?? or >2 (old ones redetected)
                        logger.eventlog.error('Found %d Cache LVs for %s in update' % (len(self.cachepvds),str(self)))
                        return (1,'Found %d Cache LVs for %s in update' % (len(self.cachepvds),str(self)))

                    if len(self.cachepvds) == 2:
                        # if has 2 cache LVs, no DR (load): create drbd, load cache
                        (e1,path1) = ext2path(self,san_res.providers[self.cachepvds[0]])
                        (e2,path2) = ext2path(self,san_res.providers[self.cachepvds[1]])
                        print 'cache paths: ',str(path1),str(path2)
                        if e1 or e2:
                            logger.eventlog.error('valid paths not found for %s in update' % str(self))
                            return (1,'valid path not found')
                        vol1 = san_res.providers[self.cachepvds[0]].cachevg.volumes[cvolname]
                        vol2 = san_res.providers[self.cachepvds[1]].cachevg.volumes[cvolname]
                        cache_loadonly=True

                    else:
                        # else (new) : select 2 paths, create 2 LVs,
                        # create & promote DRBD, Create cache on master

                        e,path1,path2 = self._get_2_pvds_paths()
                        if e:
                            logger.eventlog.error(path1)
                            return (1,path1)

                        # create 2 cache LVs
                        (e,vol1) = path1.provider.add_lv_for_cache(self,self.cachesize)
                        if e > 1:
                            tmp='cant create Cache LV1 for %s on %s in update: %s' % (self.name,path1.provider.name,vol1)
                            logger.eventlog.error(tmp)
                            return (1,tmp)
                        (e,vol2) = path2.provider.add_lv_for_cache(self,self.cachesize)
                        if e > 1:
                            vol1.provider.cachevg.volumes.delete(vol1,force=True)
                            tmp='cant create Cache LV2 for %s on %s in update: %s' % (self.name,path2.provider.name,vol2)
                            logger.eventlog.error(tmp)
                            return (1,tmp)
                    #
                    print 'cache vols: ',str(vol1),str(vol2)

                    # create new drbd device
                    drdev = san_res.raids.add(drname,SanRaidGrp(drname,None))
                    if not drdev :
                        logger.eventlog.error('failed to create/updare dr device for cache in %s' % str(self))
                        return (1,'failed to create/updare dr device')
                    drdev.raid=RaidLevel.dr
                    drdev.iscachedr=True
                    drdev.devices=[vol1,vol2]
                    (e,txt)=drdev.update()
                    print 'create dr device:',e,txt
                    if e:
                        logger.eventlog.error('cant create Cache dr for %s , %s' % (str(self),txt))
                        return (1,'cant create Cache dr')
                    if drdev.provider is path1.provider:
                        prim=path1
                    else:
                        prim=path2

                logger.eventlog.debug('create cache on %s , loadonly: %s , drname: %s' % \
                            (drdev.provider.name, cache_loadonly, drname))
                #loadonly=(self.cachepvds<>[]) # check if we already had cache LVs

                # create CacheDev
                # on loadonly we also forcing devname update
                (e,r) = drdev.provider.create_cache(prim,drdev,cvolname,loadonly=cache_loadonly,force=cache_loadonly)
                logger.eventlog.debug('create cache response: %s %s' % (e,r))
                if e:
                    return (e, 'error creating cache on %s: %s' % (drdev.provider.name,r))
        else:
            (e,r) = self._remove_cache()
            if e:
                return (e,'error removing cache on %s: %s' % (str(self),r))
        return (0,'')

    def update(self, flags=''):
        """
        The description of update comes here.
        @param flags
        @return
        """
        _load = not self.san_interface.runmode
        self._update_params()
        if 'cachesize' in self._updatedattr or _load or 'f' in flags:
            (e,r) = self._update_cachesize()
            if e:
                if not _load:    # reset cachesize on create but not on load
                    self.cachesize=0
                return (e,r)
##           self._flush()
        return (0,'')

    def _remove_cache(self):
        """
        The description of _remove_cache comes here.
        @return
        """
        san_res = self.san_interface
        cdict = self.cachedict
        for pt in self.paths():
            if pt.cacheon:
                logger.eventlog.debug('removing cache from %s path %s' % (str(self), str(pt)))
                (e,r) = pt.provider.del_cache(self, destroy=True)
                if e:
                    return (e,r)
        if self.cachedrdev:
            pvds = [s.provider for s in self.cachedrdev.slaves()]
            if san_res.raids.has_key(self.cachedrdev.name):
                san_res.raids.delete(self.cachedrdev, force=True)
            if cdict:
                for pvd in pvds:
                    (e,r) = pvd.del_cache_lv(cdict)
                    if e:
                        logger.eventlog.error('Error removing cache lv for %s from %s' % (str(self), pvd.name))
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
        tmp= '%sd%-3d %s %-6s %-30s  Vendor: %-10s %-10s  Size: %10s' % \
           (ident,self.idx,l,self.name,self.guid.strip()[-29:],self.vendor,self.model,printsz(self.size))
        if level>0:
            tmp+='\n'+ident+'  Paths:'
            for p in self.paths.values()  : tmp+='\n'+p.show(mode,level-1,ident+'    ')
            tmp+='\n'+ident+'  Partitions:'
            for p in self.partitions.values() : tmp+='\n'+p.show(mode,level-1,ident+'    ')
            tmp+='\n'
        return tmp

    used=property(__used, lambda s,v: '')

