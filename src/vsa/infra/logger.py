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


import os
import logging
import logging.handlers

from vsa.infra.config import log_dir

if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logfile = lambda file_name: os.path.join(log_dir, file_name)
event_log_file = logfile('event.log')
audit_log_file = logfile('audit.log')
agent_log_file = logfile('agent.log')
web_log_file = logfile('webportal.log')
vsad_log_file = logfile('vsad.console.log')
srvxmlrpc_log_file = logfile('srvxmlrpc.log')

loglevel = logging.DEBUG
auditlevel = logging.DEBUG
conlevel = logging.WARNING

log_size = 1048576
log_count = 2

# Event Log
eventlog = logging.getLogger('events')
#hdlr = logging.handlers.TimedRotatingFileHandler(event_log_file, 'D', 1, 5)
hdlr = logging.handlers.RotatingFileHandler(event_log_file, maxBytes=log_size, backupCount=log_count)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(module)s %(message)s')
hdlr.setFormatter(formatter)
eventlog.setLevel(loglevel)
eventlog.addHandler(hdlr)

console = logging.StreamHandler()
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
console.setLevel(conlevel)
eventlog.addHandler(console)

# Audit Log
auditlog = logging.getLogger('audit')
#hdlr = logging.handlers.TimedRotatingFileHandler(audit_log_file, 'D', 1, 5)
hdlr = logging.handlers.RotatingFileHandler(audit_log_file, maxBytes=log_size, backupCount=log_count)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
auditlog.setLevel(auditlevel)
auditlog.addHandler(hdlr)

# Agent Log
agentlog = logging.getLogger('agent')
#hdlr = logging.handlers.TimedRotatingFileHandler(agent_log_file, 'D', 1, 5)
hdlr = logging.handlers.RotatingFileHandler(agent_log_file, maxBytes=log_size, backupCount=log_count)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(module)s %(message)s')
hdlr.setFormatter(formatter)
agentlog.setLevel(loglevel)
agentlog.addHandler(hdlr)

# Web Log
weblog = logging.getLogger('web')
hdlr = logging.handlers.RotatingFileHandler(web_log_file, maxBytes=log_size, backupCount=log_count)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(module)s %(message)s')
hdlr.setFormatter(formatter)
weblog.setLevel(loglevel)
weblog.addHandler(hdlr)

def getEventLog():
    """
    The description of getEventLog comes here.
    @return
    """
    return eventlog

##def add_syslog(addr=('localhost', logging.handlers.SYSLOG_UDP_PORT), facility=logging.handlers.SysLogHandler.LOG_USER):
##    global eventlog
##    formatter = logging.Formatter('%(asctime)s %(levelname)s %(module)s %(message)s')
##    hdlr=SysLogHandler(addr,facility)
##    hdlr.setFormatter(formatter)
##    eventlog.addHandler(hdlr)
##
class GVError(Exception):
    def __init__(self, msg):
        """
        The description of __init__ comes here.
        @param msg
        @return
        """
        Exception.__init__(self, msg)
        eventlog.exception(msg)
#        infra.logger.gvlogger.error(''.join(traceback.format_stack()[0:-2]))

class GVWarning(GVError):
    def __init__(self, msg):
        """
        The description of __init__ comes here.
        @param msg
        @return
        """
        Exception.__init__(self, msg)
        eventlog.info(msg, exc_info=True)

