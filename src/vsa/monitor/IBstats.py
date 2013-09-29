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


import os, time

class IBstats(object):
    def __init__(self, port=1, hca=0):
        """
        The description of __init__ comes here.
        @param port
        @param hca
        @return
        """
        #self.lid = lid
        self.port = int(port)
        self.hca = int(hca)

        #1024*1024/4
        self.dword = 262144
        #2^32
        #self.max = 4294967296

        counters32_location = '/sys/class/infiniband/mlx4_%d/ports/%d/counters' % (self.hca, self.port)
        counters64_location = '/sys/class/infiniband/mlx4_%d/ports/%d/counters_ext' % (self.hca, self.port)

        if os.path.isdir(counters64_location):
            counters = counters64_location
            ext = '_64'
        else:
            counters = counters32_location
            ext = ''

        xmit_data = '%s/port_xmit_data%s' % (counters, ext)
        xmit_packets = '%s/port_xmit_packets%s' % (counters, ext)
        rcv_data = '%s/port_rcv_data%s' % (counters, ext)
        rcv_packets = '%s/port_rcv_packets%s' % (counters, ext)

        xmit_wait = '%s/port_xmit_wait' % counters32_location

        self.stts = {
            'XmtData': xmit_data,
            'XmtPkts': xmit_packets,
            'RcvData': rcv_data,
            'RcvPkts': rcv_packets,
            'XmtWait': xmit_wait
        }

        self.last_rt = time.time()
        self.old_data = {}

    def read(self):
        """
        The description of read comes here.
        @return
        """
        old = self.old_data
        rt = time.time()
        interval = int(rt - self.last_rt)
        if interval < 1:
            interval = 1
        ret_stts = {}
        for i in self.stts:
            try:
                new = int(open(self.stts[i], 'r').read().strip())
            except:
                return (1, 'error reading %s' % self.stts[i])
            if not old.has_key(i):
                old[i] = new
            if new < old[i]:
                old[i] = new
            data = new - old[i]
            data = data / interval
            if 'Data' in i:
                data /= self.dword
            ret_stts[i] = data
            old[i] = new
        self.old_data = old
        self.last_rt = rt
        return (0, ret_stts)
