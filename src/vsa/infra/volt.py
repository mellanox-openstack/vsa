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


import socket, struct, array, os.path
import fcntl, sys


# offsets defined in /usr/include/linux/sockios.h on linux 2.6
#MEMBERSHIP_MASK = 0x8000
#PKEY_MASK = 0x7FFF
#SIOCGIFNETMASK = 0x891b
SIOCGIFHWADDR = 0x8927
SIOCGIFADDR = 0x8915
SIOCGIFCONF = 0x8912

SIOCGIFFLAGS = 0x8913
IFF_SLAVE=0x800

# functions needed

def get_ip_address(ifname):
    """
    The description of get_ip_address comes here.
    @param ifname
    @return
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(s.fileno(), SIOCGIFADDR, struct.pack('256s', ifname[:15]))[20:24])

def get_hw_address2(ifname):
    """
    The description of get_hw_address2 comes here.
    @param ifname
    @return
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), SIOCGIFHWADDR, struct.pack('256s', ifname[:15]))
    return ''.join(['%02x:' % ord(char) for char in info[18:24]])[:-1]

def get_hw_address1(ifname):
    """
    The description of get_hw_address1 comes here.
    @param ifname
    @return
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return fcntl.ioctl(s.fileno(),SIOCGIFHWADDR ,  struct.pack('256s', ifname[:15]))[18:24].encode("hex")

def get_hw_address(ifname):
        """
        The description of get_hw_address comes here.
        @param ifname
        @return
        """
        try:
                f=open('/sys/class/net/%s/address' %ifname, 'r')
        except IOError:
                #file does not exists
                return None
        r=f.readline().strip().split(':')
        f.close()
        if r.__len__() < 6:
                return None
        m="%s%s%s%s%s%s" % (r[-6], r[-5], r[-4], r[-3], r[-2], r[-1])
        return m

def all_interfaces():
    """
    The description of all_interfaces comes here.
    @return
    """
    max_possible = 128  # arbitrary. raise if needed.
    bytes = max_possible * 32
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    names = array.array('B', '\0' * bytes)
    outbytes = struct.unpack('iL', fcntl.ioctl(
        s.fileno(),
        SIOCGIFCONF,  # SIOCGIFCONF
        struct.pack('iL', bytes, names.buffer_info()[0])
    ))[0]
    namestr = names.tostring()
    #return [namestr[i:i+32].split('\0', 1)[0] for i in range(0, outbytes, 32)]
    lst = []
    for i in range(0, outbytes, 40):
        name = namestr[i:i+16].split('\0', 1)[0]
        ip   = namestr[i+20:i+24]
        lst.append((name, ip))
    return lst


def iface_is_slaved(iface):
    """
    The description of iface_is_slaved comes here.
    @param iface
    @return
    """
    piface=struct.pack('256s', iface[:15])
    s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    pflags=fcntl.ioctl(s.fileno(), SIOCGIFFLAGS, piface)[16:18]
    flags=struct.unpack('H', pflags)[0]
    return flags & IFF_SLAVE <> 0
