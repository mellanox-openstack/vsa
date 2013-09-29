#!/usr/bin/env python

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


from twisted.web import xmlrpc, server
from vsa.client.gui.vsaxmlrpc import VsaXmlRpc

from vsa.infra.infra import getunique, getnextspace
from vsa.model import volstr2obj
from vsa.infra.params import RaidLevel
from vsa.model.san_container import SanContainer

# constants for disk stats
RDIO=0
RDSEC=1
RDWAIT=2
RDMRG=3
WRIO=4
WRSEC=5
WRWAIT=6
WRMRG=7

KILOBYTE=1024

ValidOpts=['r','s','a','n','x']
Opt2Txt={'s':'Total','a':'Avarage','n':'Minimum','x':'Maximum'}

def findmatch(name,opts):
    """
    The description of findmatch comes here.
    @param name
    @param opts
    @return
    """
    # find if name matches one of the provided options (or starts with in case of '*')
    for o in opts:
        if o==name : return 1
        if o.endswith('*') :
            start=o[:o.find('*')]
            if name.startswith(start) : return 1
    return 0

class VSAmonitor(VsaXmlRpc):
    # Root monitoring class, dispatch monitoring sessions
    def __init__(self,san):
        """
        The description of __init__ comes here.
        @param san
        @return
        """
        VsaXmlRpc.__init__(self, allowNone=True)
        self.san=san
        self.baseport=2000
        self.udpport=[]
        self.sessions={}
        self.MonClasses={'block':BlockMonitor,'ib':IBMonitor,'ifc':IFCMonitor,'target':TgtMonitor,'server':TgtMonitor,'storage':ExtMonitor}

    def startnew(self,monclass,name='session',objs=[],interval=1,oplist='',fields=[],hist=False,udp=False,template='',meta={}, start=True):
        """
        The description of startnew comes here.
        @param monclass
        @param name
        @param objs
        @param interval
        @param oplist
        @param fields
        @param hist
        @param udp
        @param template
        @param meta
        @param start
        @return
        """
        if monclass<>'template' and monclass not in self.MonClasses.keys():
            return (1,'undefined monitoring class %s' % monclass,0)
        name=getunique(self.sessions.keys(),name)
        if not oplist or oplist == '1':
            oplist='rs'
        else:
            for i in oplist:
                if i not in ValidOpts:
                    return (1,'Invalid op: %s' % i,0)
        mc=self.MonClasses[monclass](monclass,name,objs,interval,oplist,fields,hist,meta)
        self.sessions[name]=mc
##        print 'sess:',self.sessions
        mc.san = self.san
        if udp :
            mc.udpport=self.baseport+getnextspace(self.udpport,self.baseport)
            self.udpport+=[mc.udpport]
        if start :
            (e,txt)=mc.start()
            if not txt:
                txt = "failed to start monitor"
            if e: return (1,txt,0)
        return (0,name,mc.udpport)


    def add_objs(self,name,newobjs=[]):
        """
        The description of add_objs comes here.
        @param name
        @param newobjs
        @return
        """
        if name not in self.sessions.keys() : return 1
        self.sessions[name].objs+=newobjs
        return 0

    def del_objs(self,name,objs=[]):
        """
        The description of del_objs comes here.
        @param name
        @param objs
        @return
        """
        if name not in self.sessions.keys() : return 1
        for o in objs :
             if o in self.sessions[name].objs :
                 self.sessions[name].objs.remove(o)
        return 0

    def start(self,name):
        """
        The description of start comes here.
        @param name
        @return
        """
        if name not in self.sessions.keys() : return (1,'session name %s not found' % name)
        (e,txt)=self.sessions[name].start()
        if e: return (1,txt)
        return (0,'')

    def get_headers(self,name):
        """
        The description of get_headers comes here.
        @param name
        @return
        """
        if name not in self.sessions.keys() : return 1
        return self.sessions[name].get_headers()

    def process_tick(self,name):
        """
        The description of process_tick comes here.
        @param name
        @return
        """
        if name not in self.sessions.keys() : return 1
        return self.sessions[name].process_tick()

    def get_colnames(self,name):
        """
        The description of get_colnames comes here.
        @param name
        @return
        """
        if name not in self.sessions.keys() : return 1
        return self.sessions[name].get_colnames()

    def get_data(self,name):
        """
        The description of get_data comes here.
        @param name
        @return
        """
        if name not in self.sessions.keys() : return 1
        return self.sessions[name].get_data()

    def get_datatxt(self,name):
        """
        The description of get_datatxt comes here.
        @param name
        @return
        """
        if name not in self.sessions.keys() : return 1
        return self.sessions[name].get_datatxt()

    def stop(self,name,kill=True):
        """
        The description of stop comes here.
        @param name
        @param kill
        @return
        """
        if name not in self.sessions.keys() : return 1
        e = self.sessions[name].stop()
        if kill : del self.sessions[name]
        return e

class BaseMonitor(VsaXmlRpc):
    def __init__(self,monclass,name,objs=[],interval=1,oplist=[],fields=[],hist=False,meta={}):
        """
        The description of __init__ comes here.
        @param monclass
        @param name
        @param objs
        @param interval
        @param oplist
        @param fields
        @param hist
        @param meta
        @return
        """
        VsaXmlRpc.__init__(self, allowNone=True)
        self.name=name
        self.monclass=monclass
        self.objs=objs
        self.objsex=[]
        self.interval=interval
        self.oplist=oplist
        self.fields=fields
        self.colnames=[]
        self.colunits=[]
        self.hist=hist
        self.meta=meta
        self.san = SanContainer.getInstance().get_san()
        self.udpport=0
        self.oldrt={}
        self.masks={}
        self.colformat=[]
        self.headers=''
##        self.masks={'raw':[],'sum':[],'avg':[],'min':[],'max':[]}

    def process_objs(self):
        """
        The description of process_objs comes here.
        @return
        """
        objs=self.objs
        if not objs : objs=['*']
        if objs==['**']:
            objs=[k+':' for k in self.san.providers.keys()]
        pvdlist={}
##        print 'objs:',objs
        for obj in objs :
            if ':' in obj :
                s=obj.split(':')
                opvd=s[0]; obj=s[1]
                if not self.san.providers.has_key(opvd):
                    return ('Provider %s not found' % opvd)
            else : opvd=self.san.lclprovider.name
##            print 'opvd:',opvd
            if not obj : obj='*'
            if not pvdlist.has_key(opvd): pvdlist[opvd]=[obj]
            else : pvdlist[opvd]+=[obj]
        return pvdlist

    def start(self):
        """
        The description of start comes here.
        @return
        """
        "initialize monitor"
        return 0

    def get_headers(self):
        """
        The description of get_headers comes here.
        @return
        """
        "return text format column header"
        return self.headers

    def process_tick(self):
        """
        The description of process_tick comes here.
        @return
        """
        pass

    def get_colnames(self):
        """
        The description of get_colnames comes here.
        @return
        """
        "return field names, field units for web presentation"
        return (self.colnames,self.colunits)

    def get_data(self):
        """
        The description of get_data comes here.
        @return
        """
        "return single sample data table"
        return []

    def get_datafull(self):
        """
        The description of get_datafull comes here.
        @return
        """
        "return single sample data table plus totals"
        def getcol(i,mask,fmt,line):
            """
            The description of getcol comes here.
            @param i
            @param mask
            @param fmt
            @param line
            @return
            """
            if mask[i-1]:
                return fmt[i] % line[i]
            return '-'.center(len(fmt[i] % 0))

        data=self.get_data()
##        print 'data: ',data
        tbl=[]
        if 'r' in self.oplist :
            for dline in data:
##                print 'dline: ',len(dline),dline
                tbl+=[[getcol(i,self.masks['r'],self.colformat,dline) for i in range(len(dline))]]
        if len(data)>1: # TBD skip if user didnt ask for tots
            tots=self.calctots(data)
            for o in self.oplist :
                if o<>'r' :
                    dline=[Opt2Txt[o]]+tots[o]
                    tbl+=[[getcol(i,self.masks[o],self.colformat,dline) for i in range(len(dline))]]
        return tbl

    def calctots(self,data):
        """
        The description of calctots comes here.
        @param data
        @return
        """
        csum=[d for d in data[0][1:]]
        cmax=[d for d in data[0][1:]]
        cmin=[d for d in data[0][1:]]
        for l in data[1:]:
            r=range(1,len(l))
##            print 'ctot: ',r,csum,l
            csum=[csum[i-1]+l[i] for i in r]
            cmin=[min(cmin[i-1],l[i]) for i in r]
            cmax=[max(cmax[i-1],l[i]) for i in r]
        cavg=[csum[i-1]/len(data) for i in range(1,len(data[0]))]
        return {'s':csum,'a':cavg,'n':cmin,'x':cmax}

    def get_datatxt(self):
        """
        The description of get_datatxt comes here.
        @return
        """
        "return text formated sample data "
        txt=[]
        dtbl=self.get_datafull()
        for dline in dtbl:
            txt+=[' '.join(dline)]
        txt='\n'.join(txt)
        if len(dtbl)>1 : txt+='\n'
        return txt

    def stop(self):
        """
        The description of stop comes here.
        @return
        """
        "on stop hook"
        return 0

class BlockMonitor(BaseMonitor):
    def __init__(self,monclass,name,objs=[],interval=1,oplist=[],fields=[],hist=False,meta={}):
        """
        The description of __init__ comes here.
        @param monclass
        @param name
        @param objs
        @param interval
        @param oplist
        @param fields
        @param hist
        @param meta
        @return
        """
        BaseMonitor.__init__(self,monclass,name,objs,interval,oplist,fields,hist,meta)
##        self.lineformat="%-10s %7d %10d  %5.2f  %10d %7d  %5.2f     %3d  %3d\n"
        self.headers='Device                  rIO/sec      rMB/s  rDelay   wIO/sec  wMB/s  wDelay   Merged CurrIO'
        self.colformat=['%-24s','%7d','%10d','%5.2f','%10d','%7d','%5.2f','%6d','%6d']
        self.pvds=[]
        all=[1,1,1,1,1,1,1,1]
        self.masks={'r':all,'s':[1,1,0,1,1,0,1,1],'a':all,'n':all,'x':all}

    def start(self):
        """
        The description of start comes here.
        @return
        """
        pvdlist=self.process_objs()
        if pvdlist.__class__.__name__=='str' : return (1,pvdlist)
        for pv,pobj in pvdlist.items():
            nd=[]
##            blklist=self.san.providers[pv].devdict.keys()
            blklist=[ex.blkfile for ex in self.san.providers[pv].devdict.values()]

            for d in pobj :
                if d.endswith('*') :
                    start=d[:d.find('*')]
                    for o in blklist :
                        if o.startswith(start) and o not in nd : nd+=[o]
                else :
                    if d not in blklist : return (1,'Block device %s not found' % d)
                    nd+=[d]
            pvdlist[pv]=nd
##        print 'pvdlist:',pvdlist
        self.pvds=pvdlist.keys()
        for p in self.pvds : self.oldrt[p]=0.0
        for p in pvdlist :
            for n in pvdlist[p] : self.objsex+=[p+':'+n]

        self.diskstat = {}
        self.process_tick()
        return (0,'')

    def process_tick(self):
        """
        The description of process_tick comes here.
        @return
        """
        for p in self.pvds:
            self.readstts(self.san.providers[p])

    def get_data(self):
        """
        The description of get_data comes here.
        @return
        """
        data=[]
        for o in self.diskstat.keys() :
##            print 'objex: ',o,self.objsex
            if self.objsex==[] or o in self.objsex:
                s=self.diskstat[o][2]
                if s[RDIO]==0 : rwait=0
                else : rwait=(s[RDWAIT]+0.0)/s[RDIO]
                if s[WRIO]==0 : wwait=0
                else : wwait=(s[WRWAIT]+0.0)/s[WRIO]
                data+=[[o,s[RDIO],s[RDSEC]/2048,rwait,s[WRIO],s[WRSEC]/2048,wwait,s[RDMRG]+s[WRMRG],self.diskstat[o][3]]]
        return data

    def readstts(self,pvd):
        """
        The description of readstts comes here.
        @param pvd
        @return
        """
        ret = pvd.get_stt()
        if ret[0]:
            return ret[0]
        (e,rt,dstt) = ret
        # stats=dev,blkdev,[RDIO,RDSEC,RDWAIT,RDMRG,WRIO,WRSEC,WRWAIT,WRMRG],IOCURR
        for l in dstt:
            dev=pvd.name+':'+l[0]
            newstt=[]
            for s in l[2] : newstt+=[int(s)]
            if self.diskstat.has_key(dev):
                stt=self.diskstat[dev][1]
                diff=[(newstt[i]-stt[i])/(rt-self.oldrt[pvd.name]) for i in range(len(newstt))]
            else : diff=[0]*len(newstt)
            self.diskstat[dev]=[l[1],newstt,diff,int(l[3])]
        self.oldrt[pvd.name]=rt
##        print 'rstt:',pvd.name,self.diskstat


class ExtMonitor(BlockMonitor):
    def __init__(self,monclass,name,objs=[],interval=1,oplist=[],fields=[],hist=False,meta={}):
        """
        The description of __init__ comes here.
        @param monclass
        @param name
        @param objs
        @param interval
        @param oplist
        @param fields
        @param hist
        @param meta
        @return
        """
        BlockMonitor.__init__(self,monclass,name,objs,interval,oplist,fields,hist,meta)
        self.blk2lbl={}

    def start(self):
        """
        The description of start comes here.
        @return
        """
        self.pvds=[]
        objlist=[]
        if not self.objs:
            return (1,'must specify storage object name(s)')
        for o in self.objs:
            (e,devtype,devobj)=volstr2obj(o,vtypes='drbhv',pvdin=None,chklock=False, san=self.san)
            if e:
                return (e,devtype)
            if devtype=='d':
                if devobj.exttype=='partition':
                    return (1,'no support for partition monitoring')
                i=0
                for pt in devobj.paths():
                    if pt.provider:
                        if pt.provider.name not in self.pvds:
                            self.pvds += [pt.provider.name]
                        objlist += [(o+'-pt%d' % i, pt.provider, pt)]
                        i+=1
            elif devtype=='r' and devobj.raid == RaidLevel.dr:
                for sl in devobj.slaves():
                    if sl.provider:
                        if sl.provider.name not in self.pvds:
                            self.pvds += [sl.provider.name]
                        if sl.extent:
                            objlist+=[(o+'-sl%s' % sl.name, sl.provider, sl.extent)]
            else:
                if devobj.provider:
                    if devobj.provider.name not in self.pvds:
                        self.pvds += [devobj.provider.name]
                    objlist += [(o, devobj.provider, devobj)]

        for p in self.pvds:
            self.oldrt[p]=0.0
        for (lbl, pvd, o) in objlist:
            if hasattr(o, 'cacheon') and o.cacheon and o.cachedict:
                blk = o.cachedict['sysfile']
            else:
                blk = getattr(o, 'blkfile', o.devfile)
            blkfile = pvd.name+':'+blk
            self.blk2lbl[blkfile] = '%s (%s)' % (lbl, blkfile)
            self.objsex += [blkfile]

        self.diskstat = {}
        self.process_tick()
        return (0,'')

    def get_data(self):
        """
        The description of get_data comes here.
        @return
        """
        data=BlockMonitor.get_data(self)
        for i in range(len(data)):
            if self.blk2lbl.has_key(data[i][0]):
                data[i][0] = self.blk2lbl[data[i][0]]
        return data


# stats=lid,'XmtData','RcvData','XmtPkts','RcvPkts','XmtWait'
class IBMonitor(BaseMonitor):
    def __init__(self,monclass,name,objs=[],interval=1,oplist=[],fields=[],hist=False,meta={}):
        """
        The description of __init__ comes here.
        @param monclass
        @param name
        @param objs
        @param interval
        @param oplist
        @param fields
        @param hist
        @param meta
        @return
        """
        BaseMonitor.__init__(self,monclass,name,objs,interval,oplist,fields,hist,meta)
        self.headers='IB Port (LID)       RxMB/s     RxKPkt/s    TxMB/s    TxKPkt/s    XmitW'
        self.colformat=['%-16s','%10.1f','%10.1f','%10.1f','%10.1f','%10.1f']
        self.pvds=[]
        all=[1,1,1,1,1]
        self.masks={'r':all,'s':all,'a':all,'n':all,'x':all}

    def start(self):
        """
        The description of start comes here.
        @return
        """
        pvdlist=self.process_objs()
        if pvdlist.__class__.__name__=='str' : return (1,pvdlist)
        self.pvds=pvdlist.keys()
        for p in self.pvds : self.oldrt[p]=0.0
        for p in pvdlist :
            for n in pvdlist[p] : self.objsex+=[p+':'+n]

        self.ibperf = {}
        e, m = self.process_tick()
        return (e, m)

    def process_tick(self):
        """
        The description of process_tick comes here.
        @return
        """
        for p in self.pvds:
            e, m = self.readstts(self.san.providers[p])
            if e:
                return e, m
        return 0, ''

    def get_data(self):
        """
        The description of get_data comes here.
        @return
        """
        data=[]
        for o in self.ibperf.keys() :
            r=self.ibperf[o]
            s=[o]+[r[0]/1024/1024,r[1]/1024,r[2]/1024/1024,r[3]/1024,r[4]]
            data+=[s]
        return data

    def readstts(self,pvd):
        """
        The description of readstts comes here.
        @param pvd
        @return
        """
        ret = pvd.get_ibstt()
        if ret[0]:
            return ret[0], 'Please verify that ibstat is installed.'
        (e,rt,dstt) = ret
        # stats=lid,'RcvData','RcvPkts','XmtData','XmtPkts','XmtWait'
        for l in dstt:
            dev=pvd.name+':'+l[0]
            newstt=[]
            for s in l[1:] : newstt+=[float(s)]
            newstt[0]=newstt[0]*4; newstt[2]=newstt[2]*4;
            # TBD no need for diff w -r, in future use Ext counters
            if self.ibperf.has_key(dev):
                diff=[newstt[i]/(rt-self.oldrt[pvd.name]) for i in range(len(newstt))]
            else : diff=[0]*len(newstt)
            self.ibperf[dev]=diff
##            if self.ibperf.has_key(dev):
##                stt=self.ibperf[dev][0]
##                diff=[(newstt[i]-stt[i])/(rt-self.oldrt[pvd.name]) for i in range(len(newstt))]
##            else : diff=[0]*len(newstt)
##            self.ibperf[dev]=[newstt,diff]
        self.oldrt[pvd.name]=rt
        return 0, ''
##        print 'rstt:',pvd.name,self.ibperf


class IFCMonitor(BaseMonitor):
    def __init__(self,monclass,name,objs=[],interval=1,oplist=[],fields=[],hist=False,meta={}):
        """
        The description of __init__ comes here.
        @param monclass
        @param name
        @param objs
        @param interval
        @param oplist
        @param fields
        @param hist
        @param meta
        @return
        """
        BaseMonitor.__init__(self,monclass,name,objs,interval,oplist,fields,hist,meta)
        self.headers='Interface            RxMB/s    RxKPkt/s  RxErr  RxDrop  TxMB/s    TxKPkt/s  TxErr TxDrop'
        self.colformat=['%-16s','%10.1f','%10.1f','%5d','%5d','%10.1f','%10.1f','%5d','%5d']
        self.pvds=[]
        all=[1,1,1,1,1,1,1,1]
        self.masks={'r':all,'s':all,'a':all,'n':all,'x':all}

    def start(self):
        """
        The description of start comes here.
        @return
        """
        pvdlist=self.process_objs()
        if pvdlist.__class__.__name__=='str' : return (1,pvdlist)
        self.pvds=pvdlist.keys()
        for p in self.pvds : self.oldrt[p]=0.0
        self.pvdlist=pvdlist

        self.perf = {}
        self.process_tick()
        return (0,'')

    def process_tick(self):
        """
        The description of process_tick comes here.
        @return
        """
        for p in self.pvds:
            e=self.readstts(self.san.providers[p])

    def get_data(self):
        """
        The description of get_data comes here.
        @return
        """
        data=[]
        for o in self.perf.keys() :
            r=self.perf[o][1]
            s=[o]+[r[0]/1024/1024,r[1]/1024,r[2],r[3],r[4]/1024/1024,r[5]/1024,r[6],r[7]]
            data+=[s]
        return data

    def readstts(self,pvd):
        """
        The description of readstts comes here.
        @param pvd
        @return
        """
        ret = pvd.get_ifstt()
        if ret[0]:
            return ret[0]
        (e,rt,dstt) = ret
        for l in dstt:
            if findmatch(l[0],self.pvdlist[pvd.name]):
                dev=pvd.name+':'+l[0]
                newstt=[]
                for s in l[1:] : newstt+=[float(s)]
                # TBD no need for diff w -r, in future use Ext counters
                # stt: rx (bytes,packets,errs,drop), tx (bytes,packets,errs,drop)
                diff=[0]*len(newstt)
                if self.perf.has_key(dev):
                    stt=self.perf[dev][0]
                    for i in [0,1,4,5] : diff[i]=(newstt[i]-stt[i])/(rt-self.oldrt[pvd.name])
                    for i in [2,3,6,7] : diff[i]=(newstt[i]-stt[i])
                self.perf[dev]=[newstt,diff]
        self.oldrt[pvd.name]=rt
        return 0
##        print 'rstt:',pvd.name,self.ibperf


class TgtMonitor(BaseMonitor):
    def __init__(self,monclass,name,objs=[],interval=1,oplist=[],fields=[],hist=False,meta={}):
        """
        The description of __init__ comes here.
        @param monclass
        @param name
        @param objs
        @param interval
        @param oplist
        @param fields
        @param hist
        @param meta
        @return
        """
        BaseMonitor.__init__(self,monclass,name,objs,interval,oplist,fields,hist,meta)
        self.headers='Target/Lun-Initiator            rIO/sec      rMB/s    wIO/sec  wMB/s    CurrIO  Errors'
        self.colformat=['%-30s','%7d','%10d','%10d','%7d','%6d','%6d']
        all=[1,1,1,1,1,1]
        self.masks={'r':all,'s':all,'a':all,'n':all,'x':all}

    def start(self):
        """
        The description of start comes here.
        @return
        """

        objs=self.objs
        if not objs : objs=['*']
        tglist={}
##        print 'objs:',objs

        if objs==['*']:
            for k in self.san.targets.keys() : tglist[k]=['*']
            self.monclass='target'
        else:
            if self.monclass=='target':
                for obj in objs :
                    if ':' in obj :
                        s=obj.split(':')
                        obj=s[0]; lun=s[1]
                    else : lun='*'
                    if not self.san.targets.has_key(obj):
                        return (1,'Target %s not found' % obj)
                    if not tglist.has_key(obj): tglist[obj]=[lun]
                    else : tglist[obj]+=[lun]
            else:
                for obj in objs :
                    if not self.san.servers.has_key(obj):
                        return (1,'Server %s not found' % obj)
                    for t in self.san.servers[obj].targets.keys() :
                        if not tglist.has_key(t): tglist[t]=['*']

##        print 'Tglist: ', tglist
        pvdlist={}
        for t in tglist.keys() :
            p=self.san.targets[t].device
            if p :
                if not pvdlist.has_key(p.name):
                    pvdlist[p.name]=[t]
                    self.oldrt[p.name]=0.0
                else : pvdlist[p.name]+=[t]
##        print 'pvdlist: ', pvdlist
        self.pvdlist=pvdlist
        self.tglist=tglist

        self.perf = {}
        self.process_tick()
        return (0,'')

    def process_tick(self):
        """
        The description of process_tick comes here.
        @return
        """
        for p in self.pvdlist.keys():
            e=self.readstts(p)

    def get_data(self):
        """
        The description of get_data comes here.
        @return
        """
        data = []
        kilobyt_sqr = KILOBYTE**2
        for o in self.perf.keys():
            r = self.perf[o][2]
            s = [o] + [r[1], r[0]/kilobyt_sqr, r[3], r[2]/kilobyt_sqr, r[4]+r[5], r[6]]
            data += [s]
        return data

    def readstts(self,p):
        """
        The description of readstts comes here.
        @param p
        @return
        """
        tgs=self.pvdlist[p]
        pvd=self.san.providers[p]
        tlist=[self.san.targets[t] for t in tgs]
        ret = pvd.get_tgstats(tlist)
        if ret[0]:
            return ret[0]
        (e,rt,dstt) = ret
##        print 'getstt: ',e,rt,dstt
        # ifname,rx (bytes,packets,errs,drop), tx (bytes,packets,errs,drop)
        for l in dstt:
            if l[0] in tgs and ('*' in self.tglist[l[0]] or l[1] in self.tglist[l[0]]):
                key=[l[0],l[1],l[2]] # target:lun:session_id
                dev=':'.join(key)
                si=[int(s) for s in l[3:]]
                newstt=[si[0],si[1],si[4],si[5],si[1]-si[3],si[5]-si[7],si[8]] # d_subm(sect,cmds) wr_subm(sect,cmds) currrd currwt errs
##                print 'curr: ',si[1]-si[3],si[5]-si[7]
##                for s in l[3:] : newstt+=[int(s)]
                if self.perf.has_key(dev):
                    stt=self.perf[dev][1]
                    diff=[(newstt[i]-stt[i])/(rt-self.oldrt[p]) for i in range(4)]
                    diff+=[newstt[4],newstt[5],newstt[6]-stt[6]] #errors counter not div by time
                else : diff=[0]*len(newstt)
                self.perf[dev]=[key,newstt,diff]
##                logger.eventlog.info(str(self.perf[dev])) #TBD
        self.oldrt[p]=rt
        return 0
##        print 'rstt:',pvd.name,self.ibperf

#tgt lun sid rd_subm(sect,cmds) rd_done(sect,cmds) wr_subm(sect,cmds) wr_done(sect,cmds) errs
#  1   0   2           8      3           8      3           0      0           0      0    0
#  1   1   2         400     38         400     38           0      0           0      0    1


def main():
    """
    The description of main comes here.
    @return
    """
    ibm = IBMonitor()
    ibm.start()

if __name__ == 'main':
    main()
