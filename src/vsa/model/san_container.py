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


from vsa.infra.Singleton import Singleton
from vsa.infra import logger

class SanContainer(Singleton):
    def __init__(self):
        """
        The description of __init__ comes here.
        @return
        """
        pass

    def set_san(self, san_res):
        """
        The description of set_san comes here.
        @param san_res
        @return
        """
        self.san_res = san_res

    def get_san(self):
        """
        The description of get_san comes here.
        @return
        """
        try:
            return self.san_res
        except AttributeError:
            logger.eventlog.debug("Attribute Error was raised, called SanContainer.get_san before SanContainer.set_san")
            return None



