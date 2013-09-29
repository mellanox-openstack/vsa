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


import sys
from vsa.daemon.vsa_daemon import VSADaemon
from vsa.infra import infra, logger
from vsa.infra.params import VSAD_XMLRPC_PORT

def main():
    """
    VSA Daemon Main
    """
    if len(sys.argv) < 2:
        print 'usage: {0} start|stop|restart|status'.format(sys.argv[0])
        sys.exit(2)
    if len(sys.argv) > 2:
        sport = infra.tstint(sys.argv[2], VSAD_XMLRPC_PORT)
    else:
        sport = VSAD_XMLRPC_PORT
    daemon = VSADaemon(pidfile='/var/run/vsad.pid',
                                stdout=logger.vsad_log_file, stderr=logger.vsad_log_file)
    daemon.set_port(sport)
    if 'start' == sys.argv[1]:
        daemon.start()
    elif 'stop' == sys.argv[1]:
        daemon.stop()
    elif 'restart' == sys.argv[1]:
        daemon.restart()
    elif 'status' == sys.argv[1]:
        if daemon.status():
            sys.exit(0)
        else:
            sys.exit(1)
    else:
       print 'Unknown command'
       sys.exit(2)
    sys.exit(0)

if __name__ == '__main__':
    main()
