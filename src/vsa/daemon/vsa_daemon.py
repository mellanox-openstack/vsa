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


from vsa.daemon.daemon import Daemon
from vsa.infra.params import VSAD_XMLRPC_PORT
from vsa.infra import logger
import sys
from vsa.daemon.vsa_agent import VSAAgent
import SimpleXMLRPCServer


class MyXMLRPCServer(SimpleXMLRPCServer.SimpleXMLRPCServer):
    allow_reuse_address = True

def init_static_operations():
    """
    The description of init_static_operations comes here.
    @return
    """
    pass

class VSADaemon(Daemon):
    sport = VSAD_XMLRPC_PORT

    def set_port(self, port):
        """
        The description of set_port comes here.
        @param port
        @return
        """
        self.sport = port

    def pre_start(self):
        """
        The description of pre_start comes here.
        @return
        """
        init_static_operations()
        self.server = MyXMLRPCServer(("", self.sport))
        self.server.register_instance(VSAAgent())

    def run(self):
        """
        The description of run comes here.
        @return
        """
        logger.eventlog.info('VSAD started on port %d' % self.sport)
        print 'Listening on port %d' % self.sport
        sys.stdout.flush()
        try:
            self.server.serve_forever()
        finally:
            self.server.server_close()
