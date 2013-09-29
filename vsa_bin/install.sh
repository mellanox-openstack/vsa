#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR

if [ -f common ]; then
	. common
else
	echo "Can not find common file." 1>&2
	exit 1
fi

print_help()
{
	cat <<EOF

Uage: $PROGNAME [options]

	-h	this help message
	-f	force installation
	-a	install HA packages
	
EOF
	exit 0
}

input_install()
{
	local SHORTOPTS="hfad"

	ins_ha=false
	force=false

    dryrun=false

	OPTS=$(getopt $SHORTOPTS "$@")

	if [ $? -ne 0 ]; then
	    	err "'$progname -h' for more information"
	fi

	: debug: $OPTS
	eval set -- "$OPTS"

	while [ $# -gt 0 ]; do
    		: debug: $1
    		case $1 in
        	-h)
            		print_help
            		;;
		-f)
			force=true
			shift
			;;
		-a)
			ins_ha=true
			shift
			;;
        -d)
            dryrun=true
            shift
            ;;
        	--)
            		shift
            		break
            		;;
        	*)
            		err "Internal Error: option processing error: $1"
            		;;
    		esac
	done

	do_install
}

# find flashcache rpm matching kernel version
find_flashcache_rpm() {
	flashcache=`find . -name flashcache-${ker_ver/-/?}*rpm`
	if [[ -z "$flashcache" ]]; then
		echo "* Could not find a matching flashcache package for your kernel"
	fi
}

# find drbd-km rpm matching kernel version
find_drbdkm_rpm() {
	drbdkm=`find . -name drbd-km-${ker_ver/-/?}*rpm`
	if [[ -z "$drbdkm" ]]; then
		drbdutils=""
		echo "* Could not find a matching drbd-km package for your kernel"
	fi
}

select_install_rpms()
{
	if [[ ! -e ./rpms/ ]]; then
		err "rpms directory does not exists."
	fi

	# main packages

	vsa=`find ./rpms -name "vsacli-*rpm" | grep -v -- "-ha-"`
	vsa_ha=`find ./rpms -name "vsacli-ha-*rpm"`
	tgt=`find ./rpms -name "scsi-target-utils-*rpm"`

	if [[ -z "$vsa" ]]; then
		err "vsa package not found"
	fi

	if [[ -z "$tgt" ]]; then
		err "tgtd package not found"
	fi

	vsa_version=`rpm -qp $vsa --qf "%{version} %{release}"`

    packages="perl-Config-General pyserial python-zope-interface"
    packages+=" python-crypto SOAPpy pyOpenSSL python-fpconst"
    packages+=" python-twisted-core python-twisted-conch python-twisted-web"
    packages+=" pysnmp-se python-twistedsnmp"

    if ($ins_ha) ; then
        packages+=" heartbeat libnet openhpi-libs libtool-ltdl"
    fi

    p=""
    for i in $packages; do
        a=`find ./rpms -name "$i-*rpm"`
        if [ -n "$a" ]; then
            p+=" $a"
        else
            err "Could not find package $i"
        fi
    done

    packages="$vsa $tgt $p"

    if ($ins_ha) ; then
        packages+=" $vsa_ha"
    fi

	drbdutils=`find ./rpms -name "drbd-utils-*"`
	find_drbdkm_rpm
	find_flashcache_rpm
    packages+=" $drbdutils $drbdkm $flashcache"

    : Selected packages
    : $packages
}

freshen_packages() {
	if [ -z "$freshned_packages" ]; then
		return
	fi

	echo "Updating packages..."

    : Packages to be updated
    : $freshen_packages
    if (! $dryrun) ; then
        rpm -Fvh --nosignature $freshen_packages
	fi
}

check_deps()
{
        #rpm -U --force --nosignature --test $rpms_list 2>&1 >/dev/null
	local i l f

	$force && f="--force"

	if [ -z "$packages" ]; then
		fin "Nothing to install."
	fi

    : Checking dependencies
    : $packages

	#rpm -U --force --nosignature --test $l 2>&1 >/dev/null
    rpm -Uvh $f --nosignature --test $packages
    if [[ $? != 0 ]]; then
        #err "unable to install the following rpms:\n$(rpm -qp --nosignature $l)"
        err "installation failed."
    fi
}

install_packages() {
	#rm -fr $INSTALL_LOG
	#echo "Install log: $INSTALL_LOG"
	echo "Installing packages..."
	log version $vsa_version
    : Packages to be installed
    : $packages

    if (! $dryrun) ; then
        rpm -U $f --nosignature --quiet $packages
        if [ "$?" != 0 ]; then
            err "Installation encountered an error"
        fi
        log_files install $packages
	    depmod -a > /dev/null 2>&1
    fi
}

do_install() {
	select_install_rpms
	filter_install_packages
	freshen_packages
	check_deps
	install_packages
	move_log

	# make sure drbd & flashcache are loaded
	service drbd start > /dev/null 2>&1
	service flashcache start > /dev/null 2>&1

	# make sure httpd is running and reloaded new configuration
	if [ -n "`if_installed httpd`" ]; then
		service_status httpd
		if [ "$?" != 0 ]; then
			service httpd start > /dev/null 2>&1
		else
			service httpd reload > /dev/null 2>&1
		fi
	fi
	
	if [ -n "$vsacli_was_installed" ]; then
		echo -e "\nTo reflect the changes don't forget to restart vsa by executing: vsa restart"
	else
		echo -e "\nYou can start VSA by executing: vsa start"
	fi

	selinux_status

	fin "Installation complete."
}

input_install $@
