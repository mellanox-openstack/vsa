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


# VSA Constants

ERR_TWISTED = 3
ERR_HA_SLAVE = 11
ERR_HA_TRANSITION = 12
ERR_COMPUTE_NODE = 13
ERR_LOADPVD = 15
ERR_LOADPVD_LO = 17

# Data refresh period in seconds, 0 means no periodic refresh
REFRESH_PERIOD = 60

# Communication ports
SANSRV_XMLRPC_PORT = 7080
VSAD_XMLRPC_PORT = 7081
MANHOLE_PORT = 7082

# Timeout for vsad rpc connections
VSAD_RPC_TIMEOUT = 30

MANHOLE_CREDENTIALS = { 'admin': '123456' }
WEBPORTAL_CREDENTIALS = { 'admin': '123456' }

paramopts=['vendor_id','product_id','product_rev','scsi_id','scsi_sn','removable','mode_page','sense_format','online','path','direct']
iSCSIOpts=['MaxRecvDataSegmentLength','MaxXmitDataSegmentLength','DataDigest','HeaderDigest'
,'InitialR2T','MaxOutstandingR2T','ImmediateData','FirstBurstLength','MaxBurstLength',
'DataPDUInOrder','DataSequenceInOrder','ErrorRecoveryLevel','IFMarker','OFMarker','DefaultTime2Wait',
'DefaultTime2Retain','OFMarkInt','IFMarkInt','MaxConnections','RDMAExtensions','TargetRecvDataSegmentLength'
,'InitiatorRecvDataSegmentLength','MaxOutstandingUnexpectedPDUs']

showlist=['system','config','log','version','cache','fctree']

# Enums
from enum import Enum
Transport = Enum('iser', 'iscsi')
OsType = Enum('unknown', 'linux', 'windows', 'vmware', 'other')
ObjState = Enum('unknown', 'created', 'running', 'blocked', 'error', 'absent', 'down',
        'offline', 'degraded', 'delete', 'slaved', 'other')

def IsRunning(obj):
    """
    The description of IsRunning comes here.
    @param obj
    @return
    """
    return (obj.state==ObjState.running or obj.state==ObjState.degraded)

ReqState=Enum('enabled','disabled','error')
ClusterState=Enum('master','standby','slave','none','disabled','local','transition','standalone','compute')
RaidLevel=Enum('none','0','1','5','6','10','dr','linear')
CachePolicy=Enum('fifo','lru')
IoSchedType=Enum('default','noop','cfq','deadline','anticipatory')
QualityType=Enum('unknown','slow','average','fast','fastest')
AlarmType=Enum('add', 'delete', 'state_change', 'error')


# Flash Cache
CACHEVGN = 'cache.vg'  # name of the cache volume group
CACHESEP = '._.'       # replace the ':' char
CACHEPFX = 'vcache.'   # VSA flashcache prefix
CACHECMDS = 'zero_stats','do_sync','stop_sync','reclaim_policy','write_merge','dirty_thresh_pct','fast_remove','fallow_delay'

# constants for disk stats
RDIO=0
RDSEC=1
RDWAIT=2
RDMRG=3
WRIO=4
WRSEC=5
WRWAIT=6
WRMRG=7

# log menu options
logopt=['agent','audit','event','tgt','webportal']

# error return codes
ILLEGAL_EXT_NAME = 2
EXT_IS_LOCKED = 3
EXT_NOT_FOUND = 4
EXT_NOT_RUNNING = 5
EXT_IS_PRIVATE = 6
EXT_NOT_ENABLED = 7

# SNMP
SNMP_TRAP_PORT = 162
SNMP_TRAP_COMMUNITY = 'public'
