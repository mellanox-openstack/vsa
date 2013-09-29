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


from vsa.model.san_base import SanBase
from vsa.infra.params import iSCSIOpts, OsType
from vsa.infra.config import scripts_dir

class GeneralProp(SanBase):
    set_params=[
        'basewwn', 'defaultos', 'noifconfig', 'iscsiopt', 'iscsiredirect', 'redirothernet',
        'snmpmanagers', 'hbarefresh', 'reserved_vgspace', 'default_bstype'
        ]

    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        SanBase.__init__(self,'General','General Properties')
        self.fullpath='/general'
        self.noifconfig=True
        self.defaultos=OsType.unknown
        self.basewwn='0008f1111fff0000'
        self.iscsiopt={}
        self.iscsiredirect=True
        self.hbarefresh=True
        self.redirif=''
        self.redirectcb=scripts_dir+'/vsa_redirect_callback.bash'
        self.redirothernet=False
        self.snmpmanagers=''
        self.reserved_vgspace = 10   # reserved vg space in %
        self.default_bstype = 'rdwr' # default bstype for luns

    def set_iscsiopt(self,san,key,val='',test=0):
        """
        The description of set_iscsiopt comes here.
        @param san
        @param key
        @param val
        @param test
        @return
        """
        return san.robots.set_strdict(self,key,val,test,iSCSIOpts)
