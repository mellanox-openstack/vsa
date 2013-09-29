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
import os
import glob
from time import strftime, localtime
import ConfigParser

class ExtendedConfigParser(ConfigParser.ConfigParser):
    """
    This class is used to retrieve configuration values from main configuration file (gv.cfg).
    User should use read() base class API to load configuration file to memory
    and then can get the requested values.
    """

    def safe_get(self, section, option, default=None):
        """
        Get value of option that belong to specified section - if not exist return the default value.
        @param section    section name
        @param option    option name
        @param default    default value
        @raise exception    NoSectionError or NoOptionError if no such section or option in gv.cfg
        @return    option value (string)
        """
        try:
            return self.get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            if default is None:
                raise
            else:
                #TODO: add logging
                #gvlogger.info("Can't find section '%s' option '%s' in configuration file, reverting to defaults" , section, option)
                return default

    def safe_get_bool(self, section, option, default=None):
        """
        Get boolean value of option that belong to specified section - if not exist return the default value.
        @param section    section name
        @param option    option name
        @param default    default value
        @raise exception    NoSectionError or NoOptionError if no such section or option in gv.cfg
        @return    boolean value (True or False)
        """
        try:
            return self.getboolean(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            if default is None:
                raise
            else:
                #gvlogger.info("Can't find section '%s' option '%s' in configuration file, reverting to defaults", section, option)
                return default
        except ValueError:
            if not default:
                raise
            else:
                #gvlogger.info("Can't convert value from section '%s' option '%s' in configuration file, reverting to defaults", section, option)
                return default

    def safe_get_int(self, section, option, default=None):
        """
        Get integer value of option that belong to specified section - if not exist return the default value.
        @param section    section name
        @param option    option name
        @param default    default value
        @raise exception    NoSectionError or NoOptionError if no such section or option in gv.cfg
        @return    integer value (True or False)
        """
        try:
            return int(self.safe_get(section, option, default))
        except ValueError:
            if default is None:
                raise
            else:
                #gvlogger.info("Can't convert value from section '%s' option '%s' in configuration file, reverting to defaults", section, option)
                return default

    def get_config_list(self, section, option, default=None):
        """
        Get list of objects.
        @return    list
        """
        try:
            r = [value.strip() for value in self.get(section,option).split(',')]
            return r
        except ConfigParser.NoOptionError:
            return default

    def safe_set(self, section, option, val):
        """
        Set an option inside the section with val,
        if section doe's not exists then adding one.
        @param section: section name
        @param option: option name
        @param val: option value
        """
        if not self.has_section(section):
            self.add_section(section)
        self.set(section, option, val)


def init_configs():
    """
    The description of init_configs comes here.
    @return
    """
    conf = ExtendedConfigParser()
    try:
        conf.read([vsa_conf_file])
    except ConfigParser.ParsingError, e:
        # non of the services has started, so just exit and print message directly to log file (and to stdout).
        #TODO: loggit
        #fd = open(log_file, 'w+')
        message = "%s - Configuration file was corrupted." %\
                strftime("%Y-%m-%d %X", localtime())
        #fd.write(message)
        print message
        sys.exit(0)
    else:
        return conf



root_dir = \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir)
files_dir = os.path.join(root_dir, 'files')
log_dir = os.path.join(root_dir, 'files', 'log')
conf_dir = os.path.join(root_dir, 'files', 'conf')
scripts_dir = os.path.join(root_dir, 'scripts')
bitmaps_dir = os.path.join(root_dir, 'bitmaps')

config_db = os.path.join(root_dir, 'config.db')
alarms_config = os.path.join(conf_dir, 'alrmcfg.csv')
alarms_scripts_dir = os.path.join(files_dir, 'scripts')

vsa_conf_file = os.path.join(conf_dir, 'vsa.conf')

vsa_conf = init_configs()
