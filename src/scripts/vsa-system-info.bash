#!/bin/bash
exec 2>&1

are_we_root() {
	if [[ $EUID -ne 0 ]]; then
		echo "This script must be run as root" 1>&2
		exit 1
	fi
}

are_we_root

DEF_DISTRO=rhel
DISTRO=$DEF_DISTRO
KERNEL_IB=`modinfo rdma_cm | grep filename | cut -d ":" -f 2 | xargs rpm -qf`
IPOIB_DEVS=`ls -1 /sys/class/net | grep ib[1-9]*`
OS="undefined"

_t() {
    local t=$1
    local c=${#t}
    printf -v f "%${c}s" ; printf "%s\n" "${f// /*}"
    echo $t
    printf -v f "%${c}s" ; printf "%s\n" "${f// /-}"
}

get_os() {
	release_file=""

    if [ -e /etc/redhat-release ];then
        OS="rhel"
        DISTRO="el"
        release_file="/etc/redhat-release"

    elif [ -e /etc/SuSE-release ];then
        OS="suse"
        DISTRO="sl"
        release_file="/etc/SuSE-release"

    else
            return 1
    fi

	return 0
}

get_os

basic()
{
	# distro / kernel
	if [ -n "$release_file" ]; then
		cat $release_file
	else
		echo "****** Warning: unsupported distro"
	fi

	echo "****** gathering kernel info"
	uname -a

    echo "****** memory info"
    free

	echo "****** SELinux policy state: `getenforce`"
	
	echo "****** gathering relevant services info"
	chkconfig --list | grep -E "(openib|rdma|scsi|multipath|mdmonitor|iptables|iser|vsa)"

	# storage
	echo "****** gathering all disks"
	fdisk -l

	echo "****** gathering SCSI disks"
	sg_map -i -x | sort -k 2 -n

	echo "****** gathering MD devices (Software Raid)"
	mdadm --misc --detail /dev/md*

	echo "****** gathering Multi-path devices"
	multipath -l

	# networking
	echo "****** gathering Network devices"
	ip addr show

	echo "****** ******** routing info"
	ip route show

	echo "****** ******** neibour info"
	ip neigh show

	echo "****** ******** IPoIB devices mode/mtu and TCP offloads info"
	for IPOIB_DEV in $IPOIB_DEVS; do
		local _mode=`cat /sys/class/net/$IPOIB_DEV/mode`
		local _mtu=`cat /sys/class/net/$IPOIB_DEV/mtu`
		echo "****** device $IPOIB_DEV (mode: $_mode , mtu: $_mtu)"
		ethtool -k $IPOIB_DEV
	done

	echo "****** ******** IPoIB module params"
	IPOIB_PARAMS=`ls -1 /sys/module/ib_ipoib/parameters`
	for IPOIB_PARAM in $IPOIB_PARAMS; do
		IPOIB_PARAM_VAL=`cat /sys/module/ib_ipoib/parameters/$IPOIB_PARAM`
		echo "****** $IPOIB_PARAM value is $IPOIB_PARAM_VAL"
	done

	# IB devices / stack / fabric

	echo "****** gathering IB devices"
	ibv_devinfo

	echo "****** gathering rpm providing kernel IB stack"
	echo $KERNEL_IB

	if [[ "$KERNEL_IB" =~ "kernel-ib" ]]; then
		echo "****** gathering kernel's IB stack rpm info"
		rpm -qi $KERNEL_IB
		echo "****** gathering kernel's IB stack rpm content"
		rpm -ql $KERNEL_IB
	fi

    check_chkconfig
    check_firewall
    check_mlnx_ofed
}

hardware()
{
	echo "****** gathering PCI info"
	lspci -vt

	echo "****** gethering CPU info"
	cat /proc/cpuinfo

	echo "****** gethering memory info"
	cat /proc/meminfo
}	

initiator()
{
	echo "****** gathering iscsi initiator user space rpm"
	ISCSI_RPM=`rpm -qf \`which iscsiadm\``
	echo $ISCSI_RPM

	echo "****** gathering iscsi user space rpm info"
	rpm -qi $ISCSI_RPM

	echo "****** gathering iscsi interfaces"
	iscsiadm -m iface

	echo "****** gathering iscsi nodes"
	iscsiadm -m node

	echo "****** gathering iscsi sessions"
	iscsiadm -m session -P 3

	echo "****** gathering iser modinfo"
	modinfo ib_iser

	echo "****** gathering kernel iser modinfo"
	modinfo /lib/modules/`uname -r`/kernel/drivers/infiniband/ulp/iser/ib_iser.ko

	echo "****** gathering rpm providing iser"
	modinfo ib_iser | grep filename | cut -d ":" -f 2 | xargs rpm -qf

	echo "****** gathering rpm providing libiscsi"
	modinfo libiscsi | grep filename | cut -d ":" -f 2 | xargs rpm -qf 

	echo "****** gathering rpm providing libiscsi2"
	modinfo libiscsi2 | grep filename | cut -d ":" -f 2 | xargs rpm -qf 

	echo "****** gathering iser's rpm info"
	#modinfo ib_iser | grep filename | cut -d ":" -f 2 | xargs rpm -qf | xargs rpm -qi
	local _iser=`modinfo ib_iser | grep filename | cut -d ":" -f 2 | xargs rpm -qf --quiet`
	if [[ -n $_iser ]]; then
		rpm -qi $_iser
	fi

	#echo "****** gathering iser's rpm full content"
	#modinfo ib_iser | grep filename | cut -d ":" -f 2 | xargs rpm -qf | xargs rpm -ql
}

target()
{
	#echo "****** gathering iscsi/iser target package info"
	# check tgtadm incase the package is not scsi-target-utils?
	#TGT_RPM=`rpm -qf \`which tgtadm\``
	#echo $TGT_RPM

	echo "****** gathering iscsi/iser target raw info"
	tgtadm --mode target --op show
}

check_mlnx_ofed() {
    _t "Mellanox OFED Information"
    ([ -x /usr/bin/ofed_info ] && /usr/bin/ofed_info) || echo "No Mellanox OFED found"
}

check_firewall() {
    _t "iptables rules"
    iptables -nL
}

check_chkconfig() {
    _t "chkconfig order"
    find /etc/init.d/ -name "*openibd*" -o -name "*rdma*" -o -name "*iscsi*" \
        -o -name "*isertgtd*" \
        | xargs grep -m1 chkconfig |sort -k 4 -n
}

lvm_info() {
    dmsetup_info

    _t "LVM pvdisplay"
    pvdisplay
    _t "LVM vgdisplay"
    vgdisplay
    _t "LVM lvdisplay"
    lvdisplay
}

dmsetup_info() {
    _t "dmsetup ls"
    dmsetup ls
}

pack_vsa() {
	local pack="vsa-logs-$$"
	local dest="/tmp/$pack"

	echo "****** packaging vsa logs to $dest.tgz"
	mkdir $dest
	mkdir $dest/logs

	$0 -bct > $dest/vsa_system_info.txt
	lvm_info > $dest/lvm_info.txt 2>&1
	vsa_disks_debug > $dest/vsa_disks_debug.txt
	vscli show config > $dest/vsa_running_config.txt

	cp -f /opt/vsa/files/log/*.log $dest/logs
	grep tgt /var/log/messages > $dest/logs/tgtd.log
	tail -n1000 /var/log/messages > $dest/var_log_messages

	cpfile /opt/vsa/config.db $dest
	cpfile /var/log/ha-debug $dest/logs
	cpfile /var/log/ha-log $dest/logs
	cpfile /etc/ha.d/ha.cf $dest

	tar -czf $dest.tgz -C /tmp $pack
}

cpfile() {
	local src=$1
	local dst=$2
	if [ -f $src ]; then
		cp -f $src $dst
	fi
}

pack_initiator() {
	local pack="initiator-logs-$$"
	local dest="/tmp/$pack"

	echo "****** packaging logs to $dest.tgz"
	mkdir $dest
	mkdir $dest/var_lib_iscsi

	$0 -b > $dest/basic_info.txt
	$0 -i > $dest/iscsi_initiator.txt
	$0 -f > $dest/IB_fabric.txt
	tail -n1000 /var/log/messages > $dest/var_log_messages

	cp -fr /var/lib/iscsi/* $dest/var_lib_iscsi

	tar -czf $dest.tgz -C /tmp $pack
}

vsa_info()
{
	echo "****** gathering vsa info"
	/bin/env vsa version
	/bin/env vsa status

	echo "****** gathering vscli info"
	vscli show

	echo "****** gathering vscli detailed info"
	vscli show -l2

	echo "****** gathering config db dump"
	cat /opt/vsa/config.db

	echo "****** gathering tstextents output"
	python /opt/vsa/scripts/tstextents.pyc
}

vsa_disks_debug() {
	_t "VSA disks debug"
	vscli show disks -d
}

fabric()
{
	echo "****** gathering IB fabric info"
	#FIXME - the below assumes that port 1 is active, something like the below can
	# be used to enhance that and then we can use # ibnetdiscover $ACTIVE_PORT
	#ACTIVE_PORTS=`ibstat | grep -B 1 Active | grep Port | cut -d" " -f 2 | cut -d":" -f 1`

	# according to the man page of ibnetdiscover, first criteria is first active port is chosen.
	ibnetdiscover
}

fusion()
{
	echo "****** gathering Fusion-IO device info"
	fio-status
	echo "****** gathering Fusion-IO PCI analysis"
	fio-pci-check
}

usage()
{
    err_msg=$1
    name=$(basename $0);
    if [ -n "${err_msg}" ]; then
        echo -e "ERROR:\n\t${err_msg}\n"
    fi
    echo -e "usage:"
    echo -e "\t$name [-b] [-t [-c] [-i] [-f] [-H] [-F] [-l]"
    echo -e "values:"
    echo -e "\t-b : show basic info"
    echo -e "\t-t : show target info"
    echo -e "\t-c : show vsa info"
    echo -e "\t-i : show iscsi initiator info"
    echo -e "\t-f : show IB fabric info"
    echo -e "\t-H : show node Hardware info"
    echo -e "\t-F : show Fusion-IO device info"
    echo -e "\t-l : pack vsa related information to tgz"
    echo -e "\t-L : pack initiator related information to tgz"
    echo -e "* default:"
    echo -e "\t$name -bct"
    exit 1
}

DEFAULT="bct"

if [ $# == 0 ]; then
	set -- -$DEFAULT
fi

while getopts "bcfFhHitlL" opt
do
    case ${opt} in
    b)    basic;;
    c)    vsa_info;;
    f)    fabric;;
    F)    fusion;;
    h*)   usage;;
    H)    hardware;;
    i)    initiator;;
    t)    target;;
    l)    pack_vsa;;
    L)    pack_initiator;;
    ?)    usage;;
    esac
done
