#!/bin/env python

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


import socket,sys

MSG = "pingpong"

class PingPong(object):
	def __init__(self, ip, port):
		self.ip=ip
		self.port=port
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.sock.settimeout(5)
		self.sock.bind((self.ip,self.port))

	def send(self, ip):
		addr=(ip,self.port)
		print 'ping %s:%d' % addr
		self.sock.sendto(MSG, addr)

	def recv(self):
		"""
			returns tuple (e, desc) on failure
			returns tuple (0,(ip,port)) on success
		"""
		count=0
		try:
			while True:
				count+=1
				try:
					data, addr = self.sock.recvfrom(1024)
				except socket.timeout:
					print "pong timeout"
					return (1,'timeout')
				if data==MSG:
					print 'pong from %s:%d' % addr
					return (0,addr)
				if count>5: return (1,'max retries')
		except KeyboardInterrupt:
			return (1,'keyboard interrupt')

def usage():
	print "Usage:"
	print "      Receiver: %s -r [local-ip] [port]" % sys.argv[0]
	print "      Sender:   %s -s [local-ip] [remote-ip] [port]" % sys.argv[0]

def main():
	if len(sys.argv) < 4:
		usage()
		return 1
	action=sys.argv[1].strip('-')
	local_ip=sys.argv[2]
	if action=='r':
		port=int(sys.argv[3])
		pingpong = PingPong(local_ip,port)
		e,addr = pingpong.recv()	# pong
		if e: return 1
		send_ip=addr[0]
		pingpong.send(send_ip)		# ping
		return 0
	elif action=='s':
		if len(sys.argv) < 5:
			usage()
			return 1
		send_ip=sys.argv[3]
		port=int(sys.argv[4])
		pingpong = PingPong(local_ip,port)
		pingpong.send(send_ip)		# ping
		e,addr = pingpong.recv()	# pong
		return e
	else:
		print "error arguments"
		return 1

if __name__=='__main__':
	sys.exit(main())
