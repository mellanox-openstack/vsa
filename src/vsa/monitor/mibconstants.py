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


''' MIB Constants for traps '''

# system vars
sysDesc = '.1.3.6.1.2.1.1.1.0'
sysOid = '.1.3.6.1.2.1.1.2.0'
sysName = '.1.3.6.1.2.1.1.5.0'

privateBaseOid = '.1.3.6.1.4'

# voltaire Ethernet Switches'
voltaireBase       = '.1.3.6.1.4.1.5206'
Vantage8500Oid     = '.1.3.6.1.4.1.5206.1.100'
Vantage6024Oid     = '.1.3.6.1.4.1.5206.1.101'
Vantage6048Oid     = '.1.3.6.1.4.1.5206.1.102'

# VSA - Should be defined in Voltaire MIB
VSAOid             = '.1.3.6.1.4.1.5206.1.103'

#   Traps
sysTrapControlTable                     = '1.3.6.1.4.1.5206.3.10'
sysTrapControlEnable                    = '1.3.6.1.4.1.5206.3.10.1.2'
sysTrapControlManager                   = '1.3.6.1.4.1.5206.3.10.1.3'

v2cTrapOid              = '1.3.6.1.6.3.1.1.4.1.0'
timeTicks               = '.1.3.6.1.2.1.1.3.0'

#UFM Traps
volSeverity                     = '1.3.6.1.4.1.5206.1.200.6.1.0'
volTrapCategory                 = '1.3.6.1.4.1.5206.1.200.6.2.0'
volTimestamp                    = '1.3.6.1.4.1.5206.1.200.6.3.0'
volSource                       = '1.3.6.1.4.1.5206.1.200.6.4.0'
volEventID                      = '1.3.6.1.4.1.5206.1.200.6.5.0'
volDescription                  = '1.3.6.1.4.1.5206.1.200.6.6.0'

volUFMGenericTrapOID            = '1.3.6.1.4.1.5206.1.200.12.'
