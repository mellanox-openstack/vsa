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


from vsa.infra import logger
from vsa.monitor.mibconstants import volUFMGenericTrapOID, timeTicks, v2cTrapOid,\
    volSeverity, volTrapCategory, volTimestamp, volSource, volEventID,\
    volDescription
from vsa.infra.params import SNMP_TRAP_COMMUNITY, SNMP_TRAP_PORT

"""
Send SNMP trap messages to  remote gui clients
Adjusted to UFM trap structure
"""

import time, socket

from pysnmp.mapping.udp import role

from twistedsnmp.pysnmpproto import v2c
from twistedsnmp.pysnmpproto import alpha

#===============================================================================
# from mibconstants import *
# from params import *
#===============================================================================

# Category added for compatibility with UFM traps
VSA_CATEGORY = 16

class SnmpTrap:
    ''' SNMP Trap Notificator '''
    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        ''' Initialize protocol data
        '''
        self.proto = alpha.protoVersions[alpha.protoVersionId2c]

    def send(self, source, event_id, severity, text, managers):
        """
        The description of send comes here.
        @param source
        @param event_id
        @param severity
        @param text
        @param managers
        @return
        """
        ''' Send SNMP trap to all managers
        @param source: trap source, typically object name
        @param event_id: event id
        @param severity: event severity integer value
        @param text: event formatted text
        @param managers: snmp managers string: host1:port1;host2:port2;...
        '''
        # Split string host1:port1;host2:port2;... into list of lists:
        # [[host1, port1], [host2, port2], ... ] or w/o port if not specified
        try:
            managers_list = managers.split(';')
        except:
            raise Exception('Illegal snmp managers: %s' % managers)
        if not managers_list:
            logger.eventlog.warning('Empty snmp managers list')
            return

        # Prepare trap structure
        trap = v2c.Trap()
        event_oid = volUFMGenericTrapOID + str(event_id)
        category = VSA_CATEGORY
        dt=time.strftime("%Y-%m-%d %H:%M:%S")
        time_now = int(time.time())

        # first two couples in the sentOids list are mandatory
        oids = [(timeTicks,                 self.proto.TimeTicks(time_now)),
                (v2cTrapOid,                self.proto.ObjectIdentifier(event_oid)),
                (volSeverity,               self.proto.Integer(severity)),
                (volTrapCategory,           self.proto.Integer(category)),
                (volTimestamp,              self.proto.OctetString(dt)),
                (volSource,                 self.proto.OctetString(source)),
                (volEventID,                self.proto.Integer(event_id)),
                (volDescription,            self.proto.OctetString(text))
               ]

        trap.apiGenSetCommunity(SNMP_TRAP_COMMUNITY)
        trap.apiGenGetPdu().apiGenSetVarBind(oids)
        msg = trap.encode()
        for manager in managers_list:
            # Obtain manager's ip and optionally port
            ip_port = manager.split(':')
            length = len(ip_port)
            if length is 0: raise Exception('Wrong snmp manager %s' % ip_port)
            ip = ip_port[0]
            if length is 1: port = SNMP_TRAP_PORT
            else: port = int(ip_port[1])

            mng = role.manager((ip, port))
            mng.send(msg)
            logger.eventlog.debug('Sent SNMP trap to manager %s:%d' % (ip, port))

if __name__ == '__main__':
    trap = SnmpTrap()
    trap.send(source='STAM', event_id=2, severity=3, text='VSA_MSG_TEXT', managers='172.30.49.16;172.25.5.26')
