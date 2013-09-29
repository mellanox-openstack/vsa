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


#
# Added to override the default xmlrpc_ prefix usage by none-prefix
#

from twisted.web import xmlrpc
from twisted.web.xmlrpc import _QueryFactory


class NoSuchFunction(Exception):
    pass


class VsaXmlRpc(xmlrpc.XMLRPC):
    def _getFunction(self, functionPath):
        """
        Given a string, return a function, or raise NoSuchFunction.

        This returned function will be called, and should return the result
        of the call, a Deferred, or a Fault instance.

        Override xmlrpc_ prefix by none-prefix,
        i.e. RPC method names on the client and server sides will be the same.

        If functionPath contains self.separator, the sub-handler for
        the initial prefix is used to search for the remaining path.
        """
        if functionPath.find(self.separator) != -1:
            prefix, functionPath = functionPath.split(self.separator, 1)
            handler = self.getSubHandler(prefix)
            if handler is None:
                raise NoSuchFunction(self.NOT_FOUND,
                    "no such subHandler %s" % prefix)
            return handler._getFunction(functionPath)

        f = getattr(self, "%s" % functionPath, None)
        if not f:
            raise NoSuchFunction(self.NOT_FOUND,
                "function %s not found" % functionPath)
        elif not callable(f):
            raise NoSuchFunction(self.NOT_FOUND,
                "function %s not callable" % functionPath)
        else:
            return f


class VsaQueryFactory(_QueryFactory):
    noisy = False
