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


%define name vsa
%define version master
%define rel unofficial

%define debug_package %{nil}

%if %{defined suse_version}
%define ostag sl
%define httpd_conf_path /etc/apache2/conf.d
%else
%define ostag el
%define httpd_conf_path /etc/httpd/conf.d
%endif

Name:           %{name}
Version:        %{version}
Release:        %{rel}%{?dist}
Summary:	Virtual Storage Array
Vendor:		Mellanox Technologies
Packager:	Roi Dayan <roid@mellanox.com>
Group:		Storage
License:        ASL 2.0
URL:            http://wwww.mellanox.com
Source:         %name-%{version}-%{rel}.tgz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch
Provides:	%name
Requires:	python, lvm2, mdadm, device-mapper
%if %{defined suse_version}
Requires:       sg3_utils
%else
Requires:	sg3_utils-libs, sg3_utils
%endif
Requires:	pysnmp-se, python-twistedsnmp, python-twisted-conch, python-twisted-web
Requires:	python-enum, python-IPy, python-crypto

%description
Virtual Storage Array

%package ha
Group:          Storage
Summary:	High Availability for VSA
Provides:	%name-ha
Requires:	vsa = %{version}-%{release}, heartbeat = 2.1.4
%description ha
VSA High Availability files

%prep
echo %{buildroot}
rm -rf $RPM_BUILD_ROOT
%setup -q -n %name-%{version}-%{rel}

%build

%install 
function copy_n_add_file()
{
        orig_file=$1
        dest_path=$2
        distro=$3
        directive=$4

        if [ $5 ]; then
                file_name=$5
        else
                file_name=$(basename $orig_file)
        fi

        cp $orig_file ${RPM_BUILD_ROOT}$dest_path/$file_name

        add_file $orig_file $dest_path $distro $directive $file_name
}

function add_file()
{
        file_orig_path=$1
        file_dest_path=$2
        distro=$3
        directive=$4

        if [ $5 ]; then
                file_name=$5
        else
                file_name=$(basename $file_orig_path)
        fi

        echo "$directive $file_dest_path/$file_name" >> %{_tmppath}/%name-file-list-$distro
}

function add_dirs()
{
    basedir=$1
    subdir=$2
    distro=$3

    split=${subdir//\// }
    local i
    for i in $split ; do
	basedir="$basedir/$i"
	if [ ! -d "$RPM_BUILD_ROOT/$basedir" ]; then
	    mkdir -p "$RPM_BUILD_ROOT/$basedir"
	    echo "%dir $basedir" >> %{_tmppath}/%name-file-list-$distro
	fi
    done
}

FILE_LIST_MAIN=%{_tmppath}/%name-file-list-main
FILE_LIST_HA=%{_tmppath}/%name-file-list-HA

echo -n > $FILE_LIST_MAIN
echo -n > $FILE_LIST_HA

# Delete the dir where the userspace programs were built
if [ "${RPM_BUILD_ROOT}" != "/" -a -d ${RPM_BUILD_ROOT} ] ; then rm -rf ${RPM_BUILD_ROOT} ; fi

mkdir -p ${RPM_BUILD_ROOT}

# compile and optimize python src
function compile_py() {
    local fn=$1
    local e
    # there is a trick here to check for error since in python 2.4 py_compile
    # always returns 0
    e=$(python -c "import py_compile ; py_compile.main([\"$fn\"])" 2>&1)
    test -z "$e" || return 1
    e=$(python -O -c "import py_compile ; py_compile.main([\"$fn\"])" 2>&1)
    test -z "$e" || return 1
}

# add compiled python
OPT_VSA_CLI_SOURCES_LIST=$(find src -type f -name "*.py")
for i in $OPT_VSA_CLI_SOURCES_LIST ; do
        d=${i#src/}
	d=$(dirname $d)
	add_dirs "/opt/vsa" $d main
	dest="/opt/vsa/$d"
        compile_py $i || exit 1
	copy_n_add_file ${i}c $dest main "%attr(0644,root,root)"
	copy_n_add_file ${i}o $dest main "%attr(0644,root,root)"
done

# add portal files
OPT_VSA_CLI_MISC_LIST=$(find src/vsa/client/gui/portal -type f ! -name "*.py*" ! -iname "*.pyc" ! -iname "*.pyo")
for i in $OPT_VSA_CLI_MISC_LIST ; do
        d=${i#src/}
	d=$(dirname $d)
	add_dirs "/opt/vsa" $d main
	dest="/opt/vsa/$d"
	copy_n_add_file ${i} $dest main "%attr(0644,root,root)"
done

# add scripts (python scripts were already added)
%{__install} -p -m 0755 src/scripts/add-vif %{buildroot}/opt/vsa/scripts
%{__install} -p -m 0644 src/scripts/cfg.parser %{buildroot}/opt/vsa/scripts
%{__install} -p -m 0644 src/scripts/functions %{buildroot}/opt/vsa/scripts
%{__install} -p -m 0755 src/scripts/IB_datagram.sh %{buildroot}/opt/vsa/scripts
%{__install} -p -m 0755 src/scripts/isdhcp.sh %{buildroot}/opt/vsa/scripts
%{__install} -p -m 0755 src/scripts/vsa_redirect_callback.bash %{buildroot}/opt/vsa/scripts
%{__install} -p -m 0755 src/scripts/vsa_rsync.sh %{buildroot}/opt/vsa/scripts
%{__install} -p -m 0755 src/scripts/vsa-system-info.bash %{buildroot}/opt/vsa/scripts
%{__install} -p -m 0755 src/scripts/vsauser %{buildroot}/opt/vsa/scripts
%{__install} -p -m 0644 src/scripts/common.sh %{buildroot}/opt/vsa/scripts

# add other folders and files
%{__install} -d %{buildroot}/opt/vsa
%{__install} -d %{buildroot}/opt/vsa/files
%{__install} -d %{buildroot}/opt/vsa/files/conf
%{__install} -d %{buildroot}/opt/vsa/files/log
%{__install} -d %{buildroot}/opt/vsa/files/scripts
%{__install} -p -m 0644 src/files/conf/vsa.conf %{buildroot}/opt/vsa/files/conf
%{__install} -p -m 0644 src/files/conf/alrmcfg.csv %{buildroot}/opt/vsa/files/conf
%{__install} -p -m 0644 src/vsa/model/objdef.db %{buildroot}/opt/vsa/vsa/model
%{__install} -p -m 0644 src/vsa/client/cli/help.doc %{buildroot}/opt/vsa/vsa/client/cli
%{__install} -p -m 0644 src/README %{buildroot}/opt/vsa
%{__install} -p -m 0755 src/vsad %{buildroot}/opt/vsa
%{__install} -p -m 0755 src/vsasrv %{buildroot}/opt/vsa
%{__install} -p -m 0755 src/vscli %{buildroot}/opt/vsa

# sbin files
%{__install} -d %{buildroot}/usr/sbin
%{__install} -p -m 0755 sbin/vsamon %{buildroot}/usr/sbin
%{__install} -p -m 0755 sbin/vsa %{buildroot}/usr/sbin
%{__install} -p -m 0755 sbin/vscli %{buildroot}/usr/sbin
%{__install} -p -m 0755 sbin/vscliuser %{buildroot}/usr/sbin

# service scripts
%{__install} -d %{buildroot}/etc/init.d
%{__install} -p -m 0755 etc/init.d/vsa-clean %{buildroot}/etc/init.d
%{__install} -p -m 0755 etc/init.d/vsad %{buildroot}/etc/init.d
%{__install} -p -m 0755 etc/init.d/vsasrv %{buildroot}/etc/init.d
%{__install} -p -m 0755 etc/init.d/vsam %{buildroot}/etc/init.d

# logrotate config
%{__install} -d %{buildroot}/etc/logrotate.d
%{__install} -p -m 0644 etc/logrotate.d/vsa %{buildroot}/etc/logrotate.d

# httpd config
%{__install} -d %{buildroot}%{httpd_conf_path}
%{__install} -p -m 0644 etc/httpd/conf.d/vsaportal.conf %{buildroot}%{httpd_conf_path}

# HA files
%{__install} -d %{buildroot}/opt/vsa/ha_config
%{__install} -p -m 0644 src/ha_config/common_ha %{buildroot}/opt/vsa/ha_config
%{__install} -p -m 0755 src/ha_config/config_ha.sh %{buildroot}/opt/vsa/ha_config
%{__install} -p -m 0755 src/ha_config/GenAuthkey.sh %{buildroot}/opt/vsa/ha_config
%{__install} -p -m 0755 src/ha_config/get_remote_key %{buildroot}/opt/vsa/ha_config
%{__install} -p -m 0644 src/ha_config/ha.cf.template %{buildroot}/opt/vsa/ha_config
%{__install} -p -m 0644 src/ha_config/haresources.template %{buildroot}/opt/vsa/ha_config
%{__install} -p -m 0755 etc/logd.cf %{buildroot}/etc
%{__install} -d %{buildroot}/etc/ha.d/rc.d
%{__install} -p -m 0755 etc/ha.d/rc.d/linkfail %{buildroot}/etc/ha.d/rc.d
%{__install} -p -m 0755 etc/ha.d/rc.d/vsa_ha %{buildroot}/etc/ha.d/rc.d
%{__install} -d %{buildroot}/etc/ha.d/resource.d
%{__install} -p -m 0755 etc/ha.d/resource.d/fix_arp %{buildroot}/etc/ha.d/resource.d
%{__install} -p -m 0755 etc/ha.d/resource.d/vsa %{buildroot}/etc/ha.d/resource.d
%{__install} -p -m 0755 etc/ha.d/resource.d/vsad %{buildroot}/etc/ha.d/resource.d
%{__install} -p -m 0755 etc/ha.d/resource.d/vsam %{buildroot}/etc/ha.d/resource.d
%{__install} -p -m 0755 etc/ha.d/resource.d/isertgtd %{buildroot}/etc/ha.d/resource.d

##############################

: $FILE_LIST_MAIN
: $FILE_LIST_HA
: $FILE_LIST_SOURCES

%post
# if first install
if [ "$1" = "1" ] ; then
	# add default users and groups
	echo "Adding default vsa users and groups"
	vsauser="/opt/vsa/scripts/vsauser"
	
	$vsauser -g
	$vsauser -m vsadmin
        $vsauser -n vsuser
        $vsauser -f vsfiles
	
	# add services
        echo "Configuring services"
	/sbin/chkconfig --add vsa-clean
        /sbin/chkconfig --add vsad
        /sbin/chkconfig --add vsam
        /sbin/chkconfig --add vsasrv

	# patch for /etc/lvm/lvm.conf for fio type. rhel <= 6
	if [ -f /etc/lvm/lvm.conf ]; then
		grep -q '^[^#]*types[ ]*=[ ]*\[[ ]*\"fio\", [0-9]\+[ ]* \]' /etc/lvm/lvm.conf
		if [ "$?" != 0 ]; then
			num=`grep -m1 -n 'types[ ]*=[ ]*\[[ ]*\".\+\", [0-9]\+[ ]* \]' /etc/lvm/lvm.conf | cut -d: -f1`
			if [ -n "$num" ]; then
				sed -i "$num i\\    types = [ \"fio\", 16 ]" /etc/lvm/lvm.conf
			else
				echo "Warning: couldn't patch /etc/lvm/lvm.conf for fio type."
			fi
		fi
	fi

	exit 0
fi

%preun
# if last uninstall
if [ "$1" = "0" ] ; then
	# remove services
	/usr/sbin/vsa stop > /dev/null 2>&1

        /sbin/chkconfig --del vsam
	/sbin/chkconfig --del vsad
	/sbin/chkconfig --del vsasrv
	/sbin/chkconfig --del vsa-clean

	# remove default users and groups
	echo "Removing default vsa users and groups"
	vsauser="/opt/vsa/scripts/vsauser"

        $vsauser -d vsadmin
        $vsauser -d vsuser
        $vsauser -d vsfiles
        $vsauser -k

	exit 0
fi

%files -f %{_tmppath}/%name-file-list-main
%defattr(-,root,root,-)
%dir /opt/vsa
%config(noreplace) /opt/vsa/files/conf/vsa.conf
%config(noreplace) /opt/vsa/files/conf/alrmcfg.csv
#%doc README
#%{_mandir}/man8/*
%dir /opt/vsa/files
%dir /opt/vsa/files/conf
%dir /opt/vsa/files/log
%dir /opt/vsa/files/scripts
/opt/vsa/vsa/model/objdef.db
/opt/vsa/vsa/client/cli/help.doc
/opt/vsa/README
/opt/vsa/vsad
/opt/vsa/vsasrv
/opt/vsa/vscli
/usr/sbin/vsamon
/usr/sbin/vsa
/usr/sbin/vscli
/usr/sbin/vscliuser
/opt/vsa/scripts/add-vif
/opt/vsa/scripts/cfg.parser
/opt/vsa/scripts/functions
/opt/vsa/scripts/IB_datagram.sh
/opt/vsa/scripts/isdhcp.sh
/opt/vsa/scripts/vsa_redirect_callback.bash
/opt/vsa/scripts/vsa-system-info.bash
/opt/vsa/scripts/vsauser
/opt/vsa/scripts/common.sh
/etc/init.d/vsa-clean
/etc/init.d/vsad
/etc/init.d/vsasrv
/etc/init.d/vsam
/etc/logrotate.d/vsa
%{httpd_conf_path}/vsaportal.conf

%files ha -f %{_tmppath}/%name-file-list-HA
%defattr(-,root,root,-)
%dir /opt/vsa/ha_config
/opt/vsa/scripts/vsa_rsync.sh
/opt/vsa/ha_config/common_ha
/opt/vsa/ha_config/config_ha.sh
/opt/vsa/ha_config/GenAuthkey.sh
/opt/vsa/ha_config/get_remote_key
/opt/vsa/ha_config/ha.cf.template
/opt/vsa/ha_config/haresources.template
/etc/logd.cf
/etc/ha.d/rc.d/linkfail
/etc/ha.d/rc.d/vsa_ha
/etc/ha.d/resource.d/fix_arp
/etc/ha.d/resource.d/isertgtd
/etc/ha.d/resource.d/vsam
/etc/ha.d/resource.d/vsa
/etc/ha.d/resource.d/vsad

%clean
[ "${RPM_BUILD_ROOT}" != "/" -a -d ${RPM_BUILD_ROOT} ] && rm -rf ${RPM_BUILD_ROOT}
