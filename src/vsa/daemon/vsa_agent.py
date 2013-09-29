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


import os, re, time
from vsa.daemon import tgtmng
from vsa.infra.processcall import process_call
#from daemon.vsa.vsalib import get_extents, fc_create_vport, fc_delete_vport, read_fc,\
#    get_stt, get_ibstt, get_ifstt, get_ifs, addifcmd, raid_bitmap_exists,\
#    get_mdadm_bitmap, rm_raid_bitmap, dm2dict
import traceback
from vsa.infra.drbd_config import drbd_res_dict, drbd_add, drbd_remove, drbd_reinit,\
    drbd_discard_my_data, drbdadm

#import infra, tgtmng, logger, traceback
import platform

#===============================================================================
# from drbd_config import *
# from processcall import *
# from params import *
# #from volt import iface_is_slaved
# from IBstats import *
#===============================================================================

from vsa.monitor import IBstats
from vsa.infra import logger, infra
from vsa.infra.drbd_config import drbd_overview
from vsa.infra.volt import iface_is_slaved
from vsa.infra.config import scripts_dir, bitmaps_dir


os.environ['PATH']+=":/lib/udev"

mtarget = re.compile(r'^Target (\d+): (.+)')
mlun = re.compile(r'^LUN:\s(\d+)')
msize = re.compile(r'(\d+).+')
mip = re.compile(r'.+addr:([0-9.]+).+Mask:([0-9.]+).*')
mshost = re.compile(r'host(\d+)')
mrtgt = re.compile(r'rport-(\d+):(\d+)-(\d+)')
ifaces1_re = re.compile(r'(([a-z0-9_]+)(?:[a-z0-9.:]+)?).*Link\sencap:([a-z0-9]+)\s+HWaddr\s(\S+)', re.I)
ifaces2_re = re.compile(r'\s+inet\saddr:(\S+)\s+Bcast:(\S+)\s+Mask:(\S+)', re.I)
mfrstint = re.compile(r'\D+(\d+)')
msginq=re.compile(r'Vendor\ identification:\s+?(.*?)\n\s+Product\ identification:\s+(.*?)\n\s+Product\ revision\ level:\s+(.*?)\n(?:\s+Unit\ serial\ number:\s+(.*?)\n)?')
sginq_micron = re.compile(r'.*\n\s+(?P<model>(.*))        ([^ ]+) (?P<serial>([^ ]+)) (?P<firmware>([^ ]+))\n$')

ADD_VIF = scripts_dir+'/add-vif'
IS_DHCP = scripts_dir+'/isdhcp.sh'

# constants for disk stats
RDIO=0
RDSEC=1
RDWAIT=2
RDMRG=3
WRIO=4
WRSEC=5
WRWAIT=6
WRMRG=7

# see define ARPHRD_INFINIBAND as 32 in include/linux/if_arp.h
ARPHRD_INFINIBAND = 32

def get_mdadm_bitmap(name):
    """
    The description of get_mdadm_bitmap comes here.
    @param name
    @return
    """
    dir = bitmaps_dir
    if not os.path.exists(dir):
        os.makedirs(dir)
    return '%s/%s.bitmap' % (dir, name)

def raid_bitmap_exists(name):
    """
    The description of raid_bitmap_exists comes here.
    @param name
    @return
    """
    return os.path.isfile(get_mdadm_bitmap(name))

def rm_raid_bitmap(name):
    """
    The description of rm_raid_bitmap comes here.
    @param name
    @return
    """
    if raid_bitmap_exists(name):
        os.remove(get_mdadm_bitmap(name))

def getval(path):
    """
    The description of getval comes here.
    @param path
    @return
    """
    return open("/sys/block/"+path,'r').read().strip()

IBCounters_old = ['RcvData', 'RcvPkts', 'XmtData', 'XmtPkts', 'XmtWait']
IBCounters_new = ['PortRcvData', 'PortRcvPkts', 'PortXmitData', 'PortXmitPkts', 'PortXmitWait']
RoCE_stats = {}

def get_ibstt():
    """
    The description of get_ibstt comes here.
    @return
    """
    (e,o) = process_call('ibstat | grep -E "(Port|Stat: Active|Base|Link layer|^CA )"', shell=True, log=False)
    if e:
        return (e,o,[])
    lidtxt = o.splitlines()
    t = time.time()
    stts = []
    ports = {}
    device = ''
    for ltxt in lidtxt:
        ltxt = ltxt.strip()
        #CA 'mlx4_\d'
        m = re.match(r"^CA 'mlx4_(\d+)'", ltxt)
        if m:
            hca = m.group(1)
        #Port \d:
        m = re.match(r'^Port\s(\d+)', ltxt)
        if m:
            port = m.group(1)
            ports[port] = {}
            ports[port]['link_layer'] = 'InfiniBand'
            ports[port]['hca'] = hca
        #Base lid: \d
        m = re.match(r'^Base.+\s(\d+)', ltxt)
        if m:
            lid = m.group(1)
            ports[port]['lid'] = lid
            if lid == '0':
                ports[port]['link_layer'] = 'Ethernet'
        #Link layer: \w
        m = re.match(r'Link layer: (\w+)', ltxt)
        if m:
            link_layer = m.group(1)
            ports[port]['link_layer'] = link_layer
            # mlnx ofed driver shows 'IB' while the upstream kernel ofed shows 'InfiniBand'
            if ports[port]['link_layer'] == 'IB':
                ports[port]['link_layer'] = 'InfiniBand'

    for port in ports:
            if ports[port]['link_layer'] != 'InfiniBand':
                global RoCE_stats
                hca = ports[port]['hca']
                key = hca + ':' + port
                lid = key # no lid in RoCE
                if not RoCE_stats.has_key(key):
                    RoCE_stats[key] = IBstats(port, hca)
                (e, pstt) = RoCE_stats[key].read()
            if e:
                    logger.agentlog.warn('error getting RoCE stats: hca: %s, port: %s - %s' % (hca, port, pstt))
                    pstt = {}
            else:
                # perfquery not working on RoCE
                lid = ports[port]['lid']
                (e,o) = process_call('perfquery -r %s %s' % (lid, port), log=False)
                if e:
                    return (e, o, [])
                prf = o.splitlines()
                pstt = {}
                for p in prf[-5:]:
                    m1 = mfrstint.match(p)
                    if m1:
                        pstt[p.split(':')[0]] = m1.group(1)
            #
            if IBCounters_old[0] in pstt:
                counters = IBCounters_old
            else:
                counters = IBCounters_new
            stts += [[lid] + [pstt.get(i, '0') for i in counters]]

    return (0,t,stts)

def get_ifstt():
    """
    The description of get_ifstt comes here.
    @return
    """
    stts = []
    t = time.time()
    iftxt = open('/proc/net/dev').readlines()
    for ltxt in iftxt:
        if ltxt.count(':') > 1:
            print 'error: ifstt contains multiple : ,',ltxt
        l = ltxt.strip().split(':',1)
        if l and len(l) > 1 and (l[0].startswith('eth') or l[0].startswith('ib') or l[0].startswith('bond')):
            cols = l[1].split()
            # ifname,rx (bytes,packets,errs,drop), tx (bytes,packets,errs,drop)
            stts += [[l[0]]+cols[0:4]+cols[8:12]]
    return (0,t,stts)

def read_iscsi():
    """
    The description of read_iscsi comes here.
    @return
    """
    # read iSCSI session information and assosiate with system LUNs and devices
    luns = {}
    if os.path.exists("/sys/class/iscsi_session") :
        for ses in os.listdir("/sys/class/iscsi_session") :
            spath = "/sys/class/iscsi_session/"+ses+"/"
            try:
                init = open(spath+"initiatorname").read().strip()
                target = open(spath+"targetname").read().strip()
            except:
                init='unknown'; target='unknown'
            taddr=''; tport=''
            try:
                session_dev=os.listdir(spath+"device")
            except:
                session_dev=[]

            for d in session_dev :
                if d.startswith("connection") :
                    for icn in os.listdir(spath+"device/"+d) :
                        if icn.startswith("iscsi_connection") :
                            for cnd in os.listdir(spath+"device/"+d+'/'+icn) :
                                if cnd.startswith("persistent_address") :
                                    taddr=open(spath+"device/"+d+'/'+icn+'/persistent_address').read().strip()
                                if cnd.startswith("persistent_port") :
                                    tport=open(spath+"device/"+d+'/'+icn+'/persistent_port').read().strip()
            for d in session_dev :
                if d.startswith("target") :
                    for lun in os.listdir(spath+"device/"+d) :
                        if ':' in lun : luns[lun]=(init,target,taddr+':'+tport) # TBD add target portal
    return (0,luns)

# note: supported_speeds doesn't always exists
hbafld = ['port_id','port_state','speed','port_type', 'supported_speeds', 'supported_classes', 'port_name', 'node_name','fabric_name']
rtgtfld = [ 'scsi_target_id', 'port_state', 'roles', 'port_id', 'port_name', 'node_name',  'supported_classes']

fc_create_vport = '/sys/class/fc_host/%s/vport_create'
fc_delete_vport = '/sys/class/fc_host/%s/vport_delete'

def read_fc():
    """
    The description of read_fc comes here.
    @return
    """
    global fc_create_vport, fc_delete_vport
    hbas = {}
    tgts = {}
    if os.path.exists("/sys/class/fc_host"):
        for hba in os.listdir("/sys/class/fc_host"):
            m=mshost.match(hba)
            if not m:
                continue
            spath = "/sys/class/fc_host/"+hba+"/"
            tmp = {}
            for f in hbafld:
                try:
                    tmp[f]=open(spath+f).read().strip()
                except Exception,err:
                    pass
                    #logger.agentlog.error('read_fc: %s - %s' % (spath+f,str(err)))
            tmp['host']=hba
            hbas[m.group(1)]=tmp
            tmp['vports']=[]
            for dv in os.listdir(spath+'device'):
                if dv.startswith('host'):
                    tmp['vports'] += [dv[4:]]
                elif dv.startswith('vport'):
                    for dvv in os.listdir(spath+'device/'+dv):
                        if dvv.startswith('host'):
                            tmp['vports'] += [dvv[4:]]
            try:
                if not os.path.exists(spath+'max_npiv_vports'):
                    spath="/sys/class/scsi_host/"+hba+"/"
                tmp['maxnpiv']=open(spath+'max_npiv_vports').read().strip()
                tmp['npivinuse']=open(spath+'npiv_vports_inuse').read().strip()
            except:
                pass

            if os.path.exists('/sys/class/scsi_host/'+hba+'/vport_create'):
                fc_create_vport = '/sys/class/scsi_host/%s/vport_create'
                fc_delete_vport = '/sys/class/scsi_host/%s/vport_delete'

    if os.path.exists("/sys/class/fc_remote_ports") :
        for tgt in os.listdir("/sys/class/fc_remote_ports") :
            m=mrtgt.match(tgt)
            if not m : continue
            HBT=':'.join(m.groups())
            tmp={}
            spath = "/sys/class/fc_remote_ports/"+tgt+"/"
            for f in rtgtfld :
                try:
                    tmp[f]=open(spath+f).read().strip()
                except Exception,err:
                    logger.agentlog.error('read_fc: %s - %s' % (spath+f,str(err)))
            if tmp['scsi_target_id']<>'-1' :
                HBT='%s:%s:%s' % (m.groups()[0],m.groups()[1],tmp['scsi_target_id'])
                tmp['HBT']=HBT
                tmp['host']='host'+m.group(1)
                tmp['rport']=tgt
                tgts[HBT]=tmp

    return (0,hbas,tgts)

# dmsetup info -c -o name,uuid,devno,major,minor,attr --noheadings --separator ,
# dmsetup ls --target flashcache


def readlv():
    """
    The description of readlv comes here.
    @return
    """
    lvs={}
    fld='lv_name,vg_name,lv_kernel_major,lv_kernel_minor,lv_uuid,lv_size'
    cmd=['lvdisplay','-C','--separator',';','--noheadings','-o',fld]
    (status, output) = process_call(cmd, log=False, stderr=False)
    if status != 0:
        logger.agentlog.error('error getting list of LV')
        return (1,{},{})

    for l in output.strip().splitlines():
        val = l.strip().split(';')
        tmp = {}
        tmp['lvname']=val[0]
        tmp['type']='lvm'
        tmp['vgname']=val[1]
        dev=val[2]+':'+val[3]
        tmp['blockdev']=dev
        tmp['lvuuid']=val[4]
        tmp['size']=val[5]
        lvs[dev]=tmp

    (status, output) = process_call(['dmsetup','ls','--target','flashcache'],log=False)
    if status != 0:
        logger.agentlog.error('error getting Flash cache dmsetup ls data')
        return (1,{},{})

    for l in output.strip().splitlines():
        m=re.match(r'^(\S+)\s+[(](\d+).?,.?(\d+).+',l)
        if m:
            dev = m.group(2)+':'+m.group(3)
            lvs[dev] = {
                    'type': 'cache',
                    'blockdev': dev,
                    'lvname': m.group(1)
                }

    vgs={}
    fld='vg_name,vg_attr,vg_size,vg_extent_size,vg_free_count,max_lv,max_pv,UUID'
    cmd=['vgs','--nosuffix','--noheadings','--units','s','--separator',';','-o',fld]
    (status, output) = process_call(cmd, log=False, stderr=False)
    if status != 0:
        logger.agentlog.error('error getting list of VGs')
        return (1,{},{})

    for l in output.strip().splitlines():
        val = l.strip().split(';')
        tmp = {}
        tmp['vgname']=val[0]
        tmp['attr']=val[1]
        tmp['size']=val[2]
        tmp['ext']=val[3]
        tmp['free']=val[4]
        tmp['maxlv']=val[5]
        tmp['maxpv']=val[6]
        tmp['uuid']=val[7]
        tmp['slaves']=[]
        vgs[val[0]]=tmp

    fld='+pv_pe_count,pv_pe_alloc_count'
    cmd=['pvs','--nosuffix','--noheadings','--units','s','--separator',';','-o',fld]
    (status, output) = process_call(cmd, log=False, stderr=False)
    if status != 0:
        logger.agentlog.error('error getting list of PVs')
        return (1,{},{})

    for l in output.strip().splitlines():
        val = l.strip().split(';')
        tmp = {}
        tmp['pv']=val[0]
        tmp['fmt']=val[2]
        tmp['attr']=val[3]
        tmp['psize']=val[4]
        tmp['pfree']=val[5]
        tmp['pe']=val[6]
        tmp['alloc']=val[7]
        if vgs.has_key(val[1]):
            vgs[val[1]]['slaves']+=[tmp]

    return (0,lvs,vgs)


def read_fio():
    """
    Reads FusionIO block devices for product number and serial number.
    @return dictionary where the key is device name and value is tuple of PN and SN.
    """
    fio_status_result = {}
    try:
        fiopath = '/usr/bin/fio-status'
        if not os.path.isfile(fiopath):
            fiopath = '/bin/fio-status'
        if not os.path.isfile(fiopath):
            return {}
        (status, output) = process_call(['fio-status'], timeout=5, log=False)
        if status != 0:
            return {}
        lines = output.splitlines()
        model = {}
        for i in range(len(lines)):
            m = re.match(r"(fct[0-9]+):\s*Product Number:(.[^, ]+)", lines[i].strip())
            if m:
                model[m.group(1)] = m.group(2)
            m = re.match(r"(fct[0-9]+).+'(fio[a-z])'", lines[i].strip())
            if m:
                m1 = re.match(r".+Number:(.+) SN:([a-zA-Z0-9_-]+)", lines[i+1].strip())
                if m1:
                    fio_status_result[m.group(2)] = m1.groups()
                    continue
                m1 = re.match(r".+ SN:([a-zA-Z0-9_-]+)", lines[i+1].strip())
                if m1:
                    if m.group(1) in model:
                        my_model = model[m.group(1)]
                    else:
                        my_model = ''
                    my_sn = m1.group(1)
                    fio_status_result[m.group(2)] = (my_model, my_sn)
        return fio_status_result

    except Exception, err:
	logger.agentlog.error('read_fio: %s' % str(err))
        return {}


def get_ifs():
    """
    The description of get_ifs comes here.
    @return
    """
    r = []
    i = 0
    (e, o) = process_call(['/sbin/ifconfig'], log=False)
    if e:
        return (1, o)
    ls = o.splitlines()
    if os.path.isfile('/sbin/ethtool'):
        ET = True
    else:
        ET = False
    while 1:
        if i >= len(ls):
            break
        m = ifaces1_re.match(ls[i])
        if m:
            iface = m.group(1)
            parent = m.group(2)
            if re.match('^[a-z]+[0-9]+\.[0-9]+$', iface):
                vlan = True
            else:
                vlan = False
            iface_type = m.group(3)
            iface_hwaddr = m.group(4)[:17]
            l = [iface, iface_type, iface_hwaddr]
            i = i + 1
            m2 = ifaces2_re.match(ls[i])
            if m2 != None:
                l.extend(m2.groups())
            else:
                l.extend(['0.0.0.0', '0.0.0.0', '0.0.0.0'])
            (e, dhcp) = process_call([IS_DHCP, iface], log=False)
            if e:
                dhcp = ''
            l += [dhcp.strip()]
            l.append(parent)
            try:
                slaved = iface_is_slaved(iface)
            except IOError, e:
                logger.agentlog.error('get_ifs: Error reading interface %s: %s' % (iface, e.strerror))
                i = i + 1
                continue
            if slaved:
                state = 'slaved'
            else:
                try:
                    if vlan:
                        carrier = iface
                    else:
                        carrier = parent
                    f = open('/sys/class/net/' + carrier + '/carrier')
                    if f.read().strip() == '1':
                        state = 'running'
                    else:
                        state = 'down'
                    f.close()
                except IOError:
                    state = 'down'
            l.append(state)
            speed = 0
            f = open('/sys/class/net/' + parent + '/type')
            if f.read().strip() == `ARPHRD_INFINIBAND`:
                speed = '40000'
            elif ET:
                if vlan:
                    ET_iface = parent
                else:
                    ET_iface = iface
                (e, o) = process_call(['ethtool', ET_iface], log=False)
                if e == 0:
                    tmp = o[o.find('Speed'):].split()
                    if len(tmp) > 1:
                        m = re.match('[0-9]+', tmp[1])
                        if m:
                            speed = m.group(0)
            f.close()
            l.append(speed)
            r.append(l)
        i = i + 1
    return (0, r)
# ['eth0', 'Ethernet', '08:00:27:F7:87:63', '10.0.2.15', '10.0.2.255', '255.255.255.0', 'dhcp', 'parent', 'state', 'speed']

def get_stt():
    """
    The description of get_stt comes here.
    @return
    """
    stats=[]
    ds=open('/proc/diskstats','r').read().strip().splitlines()
    t= time.time()
    for l in ds:
        c=l.split()
        dev=c[2]
        if dev[0:3]<>'ram':
            # stats=dev,blkdev,[RDIO,RDSEC,RDWAIT,RDMRG,WRIO,WRSEC,WRWAIT,WRMRG],IOCURR
            newstt=[dev,c[0]+':'+c[1],[c[3],c[5],c[6],c[4],c[7],c[9],c[10],c[8]],c[11]]
            stats+=[newstt]
    return (0,t,stats)

def query_scsi_id(blk):
    """
    The description of query_scsi_id comes here.
    @param blk
    @return
    """
    if platform.dist()[0].lower() == 'redhat' and float(platform.dist()[1]) < 6:
        e,sid=process_call('scsi_id -g -x -a -s /block/'+blk, log=False)
    else:
        e,sid=process_call('scsi_id --whitelisted --export --device=/dev/'+blk, log=False)
    return e,sid.lower()

def dm2dict(text):
    """
    convert dmsetup output format of 'aa (n), bb(m) ..' to a dictionary
    @param text
    @return
    """

##    res={}
##    for l in text.splitlines():
##        items=l.strip().split(',')
##        for i in items:
##            m=re.match(r'(.*)\((\S+)\)',i.strip())
##            if m : res[m.group(1).strip()]=m.group(2).strip()
##    return res

    key=''; val=''; inside=False
    res={}
    for ch in text :
        if ch==',' : continue
        if ch=='(' :
            inside=True
            continue
        if ch==')' :
            inside=False
            res[key.strip()]=val.strip()
            key=''; val=''
            continue
        if ch==':' and not inside:
            key=''; val=''
            continue
        if inside: val+=ch
        else : key+=ch
    return res

def get_extents():
    """
    discover local storage resources and return it as a data structure
    @return
    """

    extents=[]
    mpoints={}
    swaps=[]
    (s1,lv,vgs)=readlv()
    (s2,iscsi_luns)=read_iscsi()
    (e,hbas,tgts)=read_fc()
    (e,drbds)=drbd_overview()
    fdir = read_fio()

    # read mounts
    e,o=process_call('mount | grep "^/dev"', shell=True, log=False)
    if e:
        print "error running mount: ",o
        return (e,"error running mount")
    else:    mps=o.splitlines()
    for part in mps:
        l=part.split()
        if len(l)>4 and l[1]=='on' : mpoints[l[0]]=l[2]

    # read swaps
    f=open("/proc/swaps")
    swps=f.readlines()
    f.close()
    for part in swps:
        l=part.split()
        if len(l)>4 and l[1]=='partition' : swaps.append(l[0])

    if os.path.isfile('/usr/bin/sg_inq'): DO_SGINQ=1
    else: DO_SGINQ=0

    if s1 or s2:
        print "error getting list of LV or iSCSI"
        return (1,"error getting list of LV or iSCSI")

    for vgk,vgv in vgs.items():
        tmp={}
        tmp['extype']='vg'
        tmp['state']='unknown'
        tmp['devfile']=vgk
        for k,v in vgv.items():
            tmp[k]=v
        extents += [tmp]

    for blk in sorted(os.listdir("/sys/block")) :
        if blk[0:2] in ['sd','hd','dm','fi','md','dr'] \
        or blk.startswith('rssd') \
        or blk.startswith('cciss') \
        or blk.startswith('vgc') :
            # cciss  : HP Array
            # vgc    : Virident Flash (drives: vgcX , partitions: vgcXY X=[a-h], Y=[0-7])
            # rssd   : Micron P320 (rssdX)
            blkparams=os.listdir("/sys/block/"+blk)
            blkparams.sort()
            tmp={}
            tmp['devfile']=blk
            tmp['sysfile']=blk
            tmp['blockdev']=getval(blk+'/dev')
            tmp['size']=getval(blk+'/size')     # in sectors e.g. /512
            tmp['removable']=getval(blk+'/removable')
            tmp['state']='unknown'

            if blk[0:2]=='sd':
                tmp['extype']='physical'
                tmp['type']='disk'
                tmp['state']=getval(blk+'/device/state')
                e,sid=query_scsi_id(blk)
                if e:
                    tmp['state']='absent'
                else:
                    for l in sid.splitlines():
                        ls=l.split('=')
                        if len(ls) > 1:
                            ls1=ls[1].strip()
                            tmp[ls[0][3:]]=ls1
                            if ls[0]=='id_serial' and ls1 : tmp['guid']=ls1
                if DO_SGINQ :
                    (e,o)=process_call(['sg_inq','/dev/'+blk],log=False)
                    if e : tmp['state']='absent'
                    else :
                        m=msginq.search(o)
                        if m :
                            [tmp['vendor'],tmp['model'],tmp['revision'],tmp['serial']]=m.groups('Unknown')

                devlist=os.listdir("/sys/block/"+blk+'/device')
                tmp['usedby']=[]
                for v in devlist:
                    if v[0:9]=='scsi_disk' :
                        if v=='scsi_disk':
                            v2=os.listdir("/sys/block/"+blk+'/device/scsi_disk')
                            tmp['HBTL']=v2[0]
                        else:
                            tmp['HBTL']=v[10:]
                    if v[0:12]=='scsi_generic' :
                        if v=='scsi_generic':
                            v2=os.listdir("/sys/block/"+blk+'/device/scsi_generic')
                        else:
                            tmp['sg']=v[13:]
                if iscsi_luns.has_key(tmp['HBTL']) :
                    tmp['hbatype']='iscsi'
                    tmp['it']=iscsi_luns[tmp['HBTL']]
                HBT=':'.join(tmp['HBTL'].split(':')[0:3])
                if HBT in tgts.keys():
                    tmp['hbatype']='fc'
                    tmp['it']=(tgts[HBT]['host'],tgts[HBT]['node_name'],tgts[HBT]['port_name'])

            if blk[0:2]=='hd':
                tmp['extype']='physical'
                tmp['hbatype']='ata'
                tmp['type']=getval(blk+'/device/media')
                tmp['state']='running'

            if blk.startswith('rssd'):
                tmp['extype'] = 'physical'
                tmp['hbatype'] = 'rssd'
                tmp['state'] = 'running'
                tmp['type'] = 'disk'
                tmp['vendor'] = 'Micron'

                if DO_SGINQ:
                    e, o = process_call(['sg_inq', '/dev/'+blk], log=False)

                    if e:
                        tmp['state'] = 'absent'
                    else:
                        m = sginq_micron.search(o)
                        if m:
                            g = m.groupdict()
                            tmp['model'] = g['model']
                            tmp['serial'] = g['serial']
                            tmp['guid'] = '1' + tmp['serial']

            if blk.startswith('cciss'):
                tmp['devfile']=blk.replace('!','/')
                tmp['extype']='physical'
                tmp['hbatype']='cciss'
                tmp['state']='running'
                tmp['type']='disk'

            if blk[0:3]=='vgc':
                tmp['extype']='physical'
                tmp['state']='running'
                tmp['type']='disk'
                tmp['hbatype']='vgc'

            if blk[0:2]=='dm':
                tmp['state']='running' # TBD check LV state
                tmp['extype']='dm'
                tmp['dm']=blk
                if lv.has_key(tmp['blockdev']):
                    tmp['basedon']=os.listdir("/sys/block/"+blk+'/slaves')
                    mylv=lv[tmp['blockdev']]
                    if mylv['type']=='cache':
                        tmp['extype']='cache'
                        tmp['devfile']='mapper/'+mylv['lvname']
                        (e,o)= process_call(['dmsetup','table',mylv['lvname']],log=False)
                        if e : logger.agentlog.info(' error with dmsetup table %s \n' % mylv['lvname'] + o)
                        cacheinfo=dm2dict(o)
                        ssddev=cacheinfo.get('ssd dev','')
                        tmp['ssd']=infra.iif(ssddev.startswith('/dev/'),ssddev[5:])
                        slowdev=cacheinfo.get('disk dev','')
                        tmp['slow']=infra.iif(slowdev.startswith('/dev/'),slowdev[5:])
                        tmp['cached']=cacheinfo.get('cached blocks','')
                        tmp['cachepcnt']=cacheinfo.get('cache percent','')
                        tmp['nr_queued']=cacheinfo.get('nr_queued','')
                        tmp['dirtyblk']=cacheinfo.get('dirty blocks','')
                        tmp['dirtypcnt']=cacheinfo.get('dirty percent','')
                        tmp['cname']=mylv.get('lvname','')
                    else :
                        tmp['extype']='virtual'
                        tmp['devfile']=mylv['vgname']+'/'+mylv['lvname']
#                        tmp['devfile']='mapper/'+mylv['vgname']+'-'+mylv['lvname']
                        for k in ['lvname','vgname','lvuuid'] :
                            tmp[k]=mylv[k]
                        tmp['basedon']=[mylv['vgname']]

            if blk[0:2]=='md':
                tmp['extype']='raid'
                tmp['basedon']=os.listdir("/sys/block/"+blk+'/slaves')
                tmp['level']=getval(blk+'/md/level')
                tmp['astate']=getval(blk+'/md/array_state')
                tmp['mdver']=getval(blk+'/md/metadata_version')
                if tmp['astate']=='clear' and not tmp['basedon'] : continue
                (e,o)=process_call(['mdadm','-D','/dev/'+blk],log=False)
                if not e :
                    for l in o.splitlines():
                        fl=l.split(':',1)
                        fk=fl[0].lower().strip()
                        if fk in ['name','uuid','state','rebuild status']:
                            tmp[fk]=fl[1].strip()
                    if tmp.has_key('name') and ':' in tmp['name']:
                        tmp['name']=tmp['name'].split(" ")[0].split(":")[1]
                    m=msginq.search(o)
                    if m :
                        [tmp['vendor'],tmp['model'],tmp['revision'],tmp['serial']]=m.groups('Unknown')
                slaves=[]
                for i in os.listdir("/sys/block/"+blk+'/md'):
                    if i.startswith('dev-'):
                        slot=getval(blk+'/md/'+i+'/slot')
                        state=getval(blk+'/md/'+i+'/state')
                        errors=getval(blk+'/md/'+i+'/errors')
                        slaves+=[[i[4:],slot,state,errors]]
                tmp['slaves']=slaves

            if blk.startswith('drbd'):
                tmp['extype']='dr'
                if not blk[4:] in drbds.keys(): continue
                d=drbds[blk[4:]]
                tmp['guid']=d['name']
                tmp['cs']=d['cstate'].lower()
                tmp['ds']=d.get('disk','').lower()
                tmp['ro']=d.get('role','').lower()
                tmp['basedon']=[d['dev'][5:]]
                tmp['state']='running'
                tmp['minor']=d['minor']
                tmp['resynced_percent']=d.get('resynced_percent','').lower()

            if blk[0:3]=='fio':
                tmp['extype']='physical'
                tmp['hbatype']='fio'
                tmp['type']='disk'
                tmp['state']='running'
                if fdir.has_key(blk):
                    [
                      tmp['vendor'],
                      tmp['model'],
                      tmp['revision'],
                      tmp['serial']
                    ] = ['Fio', fdir[blk][0], '1.0', fdir[blk][1]]
                    tmp['guid'] = '1' + tmp['serial']

            if 'extype' not in tmp:
                logger.agentlog.error('Missing extype for block device %s' % blk)
                continue

            extents+=[tmp]

            if mpoints.has_key('/dev/'+tmp['devfile']) : tmp['mount']=mpoints['/dev/'+tmp['devfile']]
            if '/dev/'+tmp['devfile'] in swaps : tmp['swap']="1"

            if blk[0:2] in ['hd','sd','fi'] \
            or blk.startswith('rssd') \
            or blk.startswith('cciss') \
            or blk.startswith('vgc') :
                for v in blkparams:
                    if v.startswith(blk) and tmp['state']<>'absent':
                        tmpc={}
                        tmpc['extype']='partition'
                        tmpc['id']=v[len(blk):]
                        tmpc['devfile']=v
                        if blk.startswith('cciss'):
                            tmpc['id']=v[len(blk)+1:]
                            tmpc['devfile']=v.replace('!','/')
                        tmpc['sysfile']=blk+'/'+v
                        tmpc['blockdev']=getval(blk+'/'+v+'/dev')
                        tmpc['size']=getval(blk+'/'+v+'/size')
                        tmpc['start']=getval(blk+'/'+v+'/start')
                        tmpc['basedon']=[blk]
                        if mpoints.has_key('/dev/'+tmpc['devfile']) : tmpc['mount']=mpoints['/dev/'+tmpc['devfile']]
                        if '/dev/'+tmpc['devfile'] in swaps : tmpc['swap']="1"
                        extents+=[tmpc]

    return (0,extents)


class VSAAgent:
    def __init__(self,ports=[]):
        """
        The description of __init__ comes here.
        @param ports
        @return
        """
        self.tgts={}
        self.tgts[0]=tgtmng.Tgtadm()
        try:
            (status, output) = process_call(['/etc/init.d/isertgtd','status'],log=False)
            if status != 0:
                logger.agentlog.error('Error with isertgtd status !')
                return
        except:
            return

        for l in output.strip().splitlines() :
            m=re.match(r'^tgtd.+(\d+),.+pid\s(\d+):',l)
            if m :
                pid=int(m.group(1))
                self.tgts[pid]=tgtmng.Tgtadm(pid)
                self.tgts[pid].process=int(m.group(2))

    def get_pvdinfo(self,quick=False):
        """
        The description of get_pvdinfo comes here.
        @param quick
        @return
        """
        #TBD not using quick anymore. could be removed
        info = {}
        info['version'] = infra.getVersion()
        info['tgts'] = len(self.tgts)
        info['name'] = os.uname()[1].split('.')[0]
        info['fullname'] = os.uname()[1]
        e,info['uptime'] = process_call(['uptime'],log=False)
        e,info['date'] = process_call(['date','+%T,%a,%D,%z'],log=False)
        info['cluster'] = self.get_cluster_state()
        return info

    def get_cluster_state(self):
        """
        The description of get_cluster_state comes here.
        @return
        """
        cl_status = infra.ha_rsc_status()
        if cl_status == 'none':
            cl_status = 'standby'
        elif cl_status == 'all':
            cl_status = 'master'
        elif cl_status == 'transition':
            pass
        elif not cl_status:
            cl_status = 'none'
        role = infra.get_vsa_role()
        if cl_status == 'none' and role:
            cl_status = role
        return cl_status

    def set_role(self, role):
        """
        The description of set_role comes here.
        @param role
        @return
        """
        e,r = infra.set_vsa_role(role)
        if e:
            logger.agentlog.error('failed to set role %s: %s' % (role, r))
        return e,r

    def get_tgtshow(self,pid=0,gettid=True):
        """
        The description of get_tgtshow comes here.
        @param pid
        @param gettid
        @return
        """
        return self.tgts[pid].get_tgtshow(gettid)

    def get_log(self,name='tgt'):
        """
        The description of get_log comes here.
        @param name
        @return
        """
        try:
            if name=='tgt':
                e,o = process_call(['grep','tgt','/var/log/messages'])
                if e:
                    return [o]
                return o.splitlines()
            else:
                return open(logger.agent_log_file).read().splitlines()
        except Exception,err:
            return [err]

    def create_target(self,pid,name='',tid=0,lld='',acl=['ALL'],params={},redir=''):
        """
        The description of create_target comes here.
        @param pid
        @param name
        @param tid
        @param lld
        @param acl
        @param params
        @param redir
        @return
        """
        return self.tgts[pid].create_target(name,tid,lld,acl,params,redir)

    def update_target(self,pid,tid=0,acl=[],params={}):
        """
        The description of update_target comes here.
        @param pid
        @param tid
        @param acl
        @param params
        @return
        """
        return self.tgts[pid].update_target(tid,acl,params)

    def del_target(self, pid, tid, force=False):
        """
        The description of del_target comes here.
        @param pid
        @param tid
        @param force
        @return
        """
        return self.tgts[pid].del_target(tid,force)

    def add_lun(self,pid,tid,lid=0,bspath='',bstype='rdwr',params={}):
        """
        The description of add_lun comes here.
        @param pid
        @param tid
        @param lid
        @param bspath
        @param bstype
        @param params
        @return
        """
        return self.tgts[pid].add_lun(tid,lid,bspath,bstype,params)

    def update_lunparam(self,pid,tid,lid=0,params={}):
        """
        The description of update_lunparam comes here.
        @param pid
        @param tid
        @param lid
        @param params
        @return
        """
        return self.tgts[pid].update_lunparam(tid,lid,params)

    def del_lun(self,pid,tid,lid,force=0):
        """
        The description of del_lun comes here.
        @param pid
        @param tid
        @param lid
        @param force
        @return
        """
        return self.tgts[pid].del_lun(tid,lid,force)

    def get_tgopt(self,pid,tid):
        """
        The description of get_tgopt comes here.
        @param pid
        @param tid
        @return
        """
##        print 'get tgopt pid:%s tid:%s' % (str(pid),str(tid))
        return self.tgts[pid].get_tgopt(tid)

    def set_tgopt(self,pid,tid,iscsiopt):
        """
        The description of set_tgopt comes here.
        @param pid
        @param tid
        @param iscsiopt
        @return
        """
        return self.tgts[pid].set_tgopt(tid,iscsiopt)

    def get_tgstats(self,tglist):
        """
        The description of get_tgstats comes here.
        @param tglist
        @return
        """
        full=[]; rt=0
        for tg in tglist:
            (pid,tid)=tuple(tg)
            # TBD can optimize, when multiple tg per proc, use -m sys (tid=-1)
            (e,rt,stt)=self.tgts[pid].get_tgstats(tid,pid)
            if e : return (e,rt,stt)
            full+=stt
        return (0,rt,full)

    def get_extents(self):
        """
        The description of get_extents comes here.
        @return
        """
        try:
            ret=get_extents() #WTF
        except Exception,err:
            logger.agentlog.error('Error! %s \n %s ' % (str(err), traceback.format_exc()))
            return (1,'error on get_extents %s \n %s ' % (str(err), traceback.format_exc()))
        return ret

    def add_vport(self,host,wwnn,wwpn):
        """
        The description of add_vport comes here.
        @param host
        @param wwnn
        @param wwpn
        @return
        """
        logger.agentlog.info('adding vport %s:%s:%s ...' % (host,wwnn,wwpn))
        logger.agentlog.debug(('echo "%s:%s" > '+fc_create_vport) % (wwpn,wwnn,host))
        try:
            fl=open(fc_create_vport % host,'w')
            fl.write('%s:%s' % (wwpn,wwnn))
            fl.close()
        except Exception,err:
            txt='failed to add vport %s:%s:%s err: %s' % (host,wwpn,wwnn,str(err))
            logger.agentlog.error(txt)
            return (1,txt)
        return (0,'')

    def del_vport(self,host,wwnn,wwpn):
        """
        The description of del_vport comes here.
        @param host
        @param wwnn
        @param wwpn
        @return
        """
        logger.agentlog.info('delete vport %s:%s:%s ...' % (host,wwnn,wwpn))
        logger.agentlog.debug(('echo "%s:%s" > '+fc_delete_vport) % (wwpn,wwnn,host))
        try:
            fl=open(fc_delete_vport % host,'w')
            fl.write('%s:%s' % (wwpn,wwnn))
            fl.close()
        except Exception,err:
            txt='failed to delete vport %s:%s:%s err: %s' % (host,wwpn,wwnn,str(err))
            logger.agentlog.error(txt)
            return (1,txt)
        return (0,'')

    def read_fc(self):
        """
        The description of read_fc comes here.
        @return
        """
        return read_fc()

    def get_stt(self):
        """
        The description of get_stt comes here.
        @return
        """
        return get_stt()

    def get_ibstt(self):
        """
        The description of get_ibstt comes here.
        @return
        """
        return get_ibstt()

    def get_ifstt(self):
        """
        The description of get_ifstt comes here.
        @return
        """
        return get_ifstt()

    def get_ifs(self):
        """
        The description of get_ifs comes here.
        @return
        """
        return get_ifs()

    def set_if(self,ifname,dhcp=False,ip='',mask='',bcast='',vlan='',mtu=0):
        """
        The description of set_if comes here.
        @param ifname
        @param dhcp
        @param ip
        @param mask
        @param bcast
        @param vlan
        @param mtu
        @return
        """
        ifstr=''
        if vlan:
            if ifname.startswith('ib') : ifstr=' --pkey '+vlan
            else : ifstr=' --vlan '+vlan
        if dhcp: ifstr+=' --method dhcp'
        else : ifstr+=' --method static --ip %s --netmask %s --broadcast %s' % (ip,mask,bcast)
        if mtu : ifstr+=' --mtu '+str(mtu)
        args=(ADD_VIF+' --vif-name '+ifname+ifstr).split()
        return process_call(args)

    def add_md(self, mdnum, name, level, drives, options, force=False, loadonly=False):
        """
        The description of add_md comes here.
        @param mdnum
        @param name
        @param level
        @param drives
        @param options
        @param force
        @param loadonly
        @return
        """
        opts = ''
        if force:
            opts += ' -f'

        if loadonly:
            if options.get('write-mostly') and raid_bitmap_exists(name):
                opts += ' --bitmap=%s' % get_mdadm_bitmap(name)
            line = 'mdadm --assemble /dev/%s%s %s' % \
              (mdnum, opts, ' '.join(drives))
        else:
            if options.get('chunk'): opts +=' -c %d' % options['chunk']
            if options.get('parity'): opts +=' -p %s' % options['parity']

            spare = options.get('spare',0)
            if spare:
                opts +=' -x%d' % spare
            len_drives = len(drives) - spare

            write_mostly=''
            if options.get('write-mostly'):
                write_mostly = ' --write-mostly ' + drives.pop()
            if options.get('write-behind') >= 0:
                opts += ' --write-behind'
                if options['write-behind'] > 0:
                    opts += '=%d' % options['write-behind']
                rm_raid_bitmap(name)
                opts += ' --bitmap=%s' % get_mdadm_bitmap(name)

            line = 'mdadm --create /dev/%s -l%s -R -e 1.0 -N %s -n%d%s %s%s' % \
              (mdnum, level, name, len_drives, opts, ' '.join(drives), write_mostly)

        (e,r) = process_call(line)
        logger.agentlog.info(r)
        print r
        return (e,r)

    def del_md(self, mdnum, name, drives=[], zero=False):
        """
        The description of del_md comes here.
        @param mdnum
        @param name
        @param drives
        @param zero
        @return
        """
        #self.del_mddev(mdnum,drives)
        (e,r2) = process_call('mdadm --manage --stop /dev/%s' % mdnum)
        if e:
            return (e,r2)
        rm_raid_bitmap(name)
        if zero:
            for d in drives:
                (e,r3) = process_call('mdadm --zero-superblock '+d)
        logger.agentlog.info('Del raid, %s ' % r2)
        return (0,r2)

    def add_mddev(self, mdnum, drives, newsize=0):
        """
        The description of add_mddev comes here.
        @param mdnum
        @param drives
        @param newsize
        @return
        """
        for d in drives:
            (e,r) = process_call('mdadm --add /dev/%s %s' % (mdnum, d))
            logger.agentlog.info(r)
            if e: return (e,r)
        if newsize:
            (e,r) = process_call('mdadm --grow /dev/%s --raid-devices=%d' % (mdnum, newsize))
            if e: return (e,r)
        return (0,'')

    def del_mddev(self, mdnum, drives):
        """
        The description of del_mddev comes here.
        @param mdnum
        @param drives
        @return
        """
        for d in drives:
            (e,r) = process_call('mdadm /dev/%s --fail %s --remove %s' % (mdnum, d, d))
            logger.agentlog.info(r)
            if e: return (e,r)
        return (0,'')

    def add_vg(self,name,drives,force=False) :
        """
        The description of add_vg comes here.
        @param name
        @param drives
        @param force
        @return
        """
        (e,r)=process_call(['pvcreate']+drives)
        logger.agentlog.info(r)
        print r
        if e: return e,r
        (e2,r2)=process_call(['vgcreate',name]+drives)
        logger.agentlog.info(r2)
        print r2
        return e2,r2

    def del_vg(self,name,drives) :
        """
        The description of del_vg comes here.
        @param name
        @param drives
        @return
        """
        (e,o)   = process_call(['vgremove',name,'-f'])
        logger.agentlog.info(o)
        print o
        if e: return e,o
        (e1,o1) = process_call(['pvremove']+drives+['-f'])
        logger.agentlog.info(o1)
        print o1
        return e1,o1

    def add_volume(self, name, pool, size, options):
        """
        The description of add_volume comes here.
        @param name
        @param pool
        @param size
        @param options
        @return
        """
        # -c, --chunksize ChunkSize
        # -i, --stripes Stripes
        # -I, --stripesize StripeSize
        # -m, --mirrors Mirrors
        # -p, --permission r|rw
        # -r, --readahead ReadAheadSectors|auto|none
        # -s, --snapshot
        opts = ''
        if options.get('stripes',0) > 0 and options.get('stripesize',0) > 0:
            opts += ' -i %d -I %d' % (options['stripes'], options['stripesize'])
        if options.get('readahead',-1) >= 0:
            opts += ' -r %d' % options['readahead']
        cmd = 'lvcreate -n %s -L %s%s %s' % (name, size, opts, pool)
        (e,o) = process_call(cmd)
        logger.agentlog.info(o)
        print o
        return (e,o)

    def extend_volume(self,volpath,size):
        """
        The description of extend_volume comes here.
        @param volpath
        @param size
        @return
        """
        cmd = 'lvextend --size %s %s' % (size, volpath)
        (e,o) = process_call(cmd)
        logger.agentlog.info(o)
        print o
        return (e,o)

    def reduce_volume(self,volpath,size):
        """
        The description of reduce_volume comes here.
        @param volpath
        @param size
        @return
        """
        cmd = 'lvreduce -f --size %s %s' % (size, volpath)
        (e,o) = process_call(cmd)
        logger.agentlog.info(o)
        print o
        return (e,o)

    def del_volume(self, vgname, lvname):
        """
        The description of del_volume comes here.
        @param vgname
        @param lvname
        @return
        """
        name = '/dev/%s/%s' % (vgname, lvname)
        for i in [0, 1, 2]:
            if i > 0:
                time.sleep(1)
            if i == 2:
                logger.agentlog.warning('failed to remove lv %s. trying to remove dm first' % name)
                (e,o) = process_call('dmsetup info %s --columns --noheadings -o name' % name)
                if not e:
                    dm = o.strip()
                    (e,o) = process_call(['dmsetup', 'remove', dm])
            (e,o) = process_call(['lvremove', name, '-f'])
            if not e:
                break
        logger.agentlog.info(o)
        print o
        return (e,o)

    def config_drbd(self,primary,res_name, drbd_dev, local_host, local_ip, local_port, local_dev, remote_host, remote_ip, remote_port, remote_dev, protocol='C',loadonly=False):
        """
        The description of config_drbd comes here.
        @param primary
        @param res_name
        @param drbd_dev
        @param local_host
        @param local_ip
        @param local_port
        @param local_dev
        @param remote_host
        @param remote_ip
        @param remote_port
        @param remote_dev
        @param protocol
        @param loadonly
        @return
        """
        drbd_d=drbd_res_dict(drbd_dev, local_host, local_ip, local_port, local_dev,
            remote_host, remote_ip, remote_port, remote_dev, protocol)
        e,r=drbd_add(res_name, drbd_d, primary, loadonly)
        if e:
            logger.agentlog.error('Error adding drbd resource: %s' % r)
            return (e,"Error adding drbd resource: %s" % r)
        return (0,'')

    def remove_drbd(self,res):
        """
        The description of remove_drbd comes here.
        @param res
        @return
        """
        e,r=drbd_remove(res)
        if e: return (e,"Error removing drbd resource: %s" % r)
        return (0,'')

    def update_drbd(self,res,opr=''):
        """
        The description of update_drbd comes here.
        @param res
        @param opr
        @return
        """
        if opr == 'reinit':
            return drbd_reinit(res)
        elif opr == 'discard-my-data':
            return drbd_discard_my_data(res)
        return drbdadm(opr,res)

    def add_cache(self,name,fast,slow,size='4',force=True):
        """
        The description of add_cache comes here.
        @param name
        @param fast
        @param slow
        @param size
        @param force
        @return
        """
        tmp=['-p', 'back', '-b',size+'k']
        if force : tmp=['-f']+tmp
        print ['flashcache_create']+tmp+[name,fast,slow]
        (e,o)= process_call(['flashcache_create']+tmp+[name,fast,slow])
##        logger.agentlog.info(o)
        print o
        return (e,o)

    def del_cache(self, name, destroydev='', force=True):
        """
        The description of del_cache comes here.
        @param name
        @param destroydev
        @param force
        @return
        """
        (e,o) = process_call(['dmsetup','remove',name])
##        logger.agentlog.info(o)
        print o
        if e:
            return (e,o)
        if destroydev:
            print 'Erasing cache meta-data from disk: '+destroydev
            tmp = []
            if force:
                tmp += ['-f']
            (e,o) = process_call(['flashcache_destroy']+tmp+[destroydev])
        return (e,o)

    def load_cache(self, fast, force=False):
        """
        The description of load_cache comes here.
        @param fast
        @param force
        @return
        """
        cmd = ['flashcache_load']
        if force:
            cmd += ['-u']
        cmd += [fast]
        (e,o) = process_call(cmd)
        logger.agentlog.info(o)
        return (e,o)

    def get_cache_stt(self,name):
        """
        The description of get_cache_stt comes here.
        @param name
        @return
        """
        (e,o)= process_call(['dmsetup','status',name])
        logger.agentlog.info(o)
        print o
        if not e : return (0,dm2dict(o))
        return (e,o)

    def act_cache(self,action):
        """
        The description of act_cache comes here.
        @param action
        @return
        """
    # actions: 'zero_stats','do_sync','stop_sync','reclaim_policy=','write_merge=','dirty_thresh_pct='
        try:
            e,o=process_call('sysctl -w dev.flashcache.'+action)
            print o
            return (e,o)
        except Exception, err:
            return (1,'error with flash cache method, '+str(err))

    def set_dev_params(self,name,params):
        """
        The description of set_dev_params comes here.
        @param name
        @param params
        @return
        """
        o=''; e=0
        if 'readahead' in params.keys():
            (e,o)= process_call(['blockdev','--setra',str(params['readahead']),'/dev/'+name])
        if 'iosched' in params.keys():
            try:
                f=open('/sys/block/%s/queue/scheduler' % name,'w')
                f.write(params['iosched'])
                f.close()
            except Exception, err:
                logger.agentlog.error('cant set ioscheduler on device '+name)
                e=1; o=str(err)
        print o
        return (e,o)

    def process_call(self,argv, ignoreOutput=False,log=True):
        """
        The description of process_call comes here.
        @param argv
        @param ignoreOutput
        @param log
        @return
        """
        o=process_call(argv,log=log)
        if ignoreOutput and o[0]==0: return (0,'')
        return o
