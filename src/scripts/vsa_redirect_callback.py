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


import sys,xmlrpclib
from vsa.infra.TimeoutTransport import TimeoutTransport
from vsa.infra.params import SANSRV_XMLRPC_PORT
#===============================================================================
# from params import *
# from TimeoutTransport import *
#===============================================================================

def redirect_callback(argv):
	if len(argv) < 3:
		print "usage: <target_name> <srcip>"
		return 1
	target = argv[1]
	srcip = argv[2]
	trans = TimeoutTransport()
	trans.set_timeout(10)
	srv = xmlrpclib.ServerProxy('http://localhost:' + str(SANSRV_XMLRPC_PORT) + '/', transport=trans, allow_none=True)
	try:
		(e,ip,port) = srv.get_target_portal(target,srcip)
	except Exception,e:
		e=1
	if e:
		# this can go also to the vsa/system log
		# print "error redirecting target %s initiator %s - reason %s\n" %(target,srcip,ip)
		print ''
	else:
		print ip + ':' + port + ':Permanent'
	return 0

if __name__ == '__main__':
	sys.exit(redirect_callback(sys.argv))
