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


import xmlrpclib, httplib

class TimeoutHTTPConnection(httplib.HTTPConnection):
    def connect(self):
        """
        The description of connect comes here.
        @return
        """
        httplib.HTTPConnection.connect(self)
        self.sock.settimeout(self.timeout)

class TimeoutHTTP(httplib.HTTP):
    _connection_class = TimeoutHTTPConnection

    def set_timeout(self, timeout):
        """
        The description of set_timeout comes here.
        @param timeout
        @return
        """
        self._conn.timeout = timeout

class TimeoutTransport(xmlrpclib.Transport):
    """Add a timeout attibute to HTTPConnection through HTTP."""
    timeout = 60

    def set_timeout(self, timeout):
        """
        The description of set_timeout comes here.
        @param timeout
        @return
        """
        self.timeout = timeout

    def make_connection(self, host):
        """
        Extends Transport.make_connection to set the timeout on the
        connection instance.
        """
        conn = TimeoutHTTP(host)
        conn.set_timeout(self.timeout)
        return conn
