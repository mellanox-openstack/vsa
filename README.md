VSA - Virtual Storage Array
===========================

Overview:
---------
Virtual Storage Array (VSA) is a software package which enable a scale-out, highly available, and high-performance SCSI/Block storage system.

It support iSCSI or iSCSI-RDMA (iSER) block storage protocols, and works over 10/40GbE and InfiniBand networks.

VSA can drive millions of IOPs per storage server, and scale bandwidth and IOPs linearly as users add more storage servers.
VSA comes with cluster wide CLI and Web based user interface.

Installation:
-------------
VSA binary RPMs are located at the RPMS folder, to install just run:
$ rpm -ivh vsa-git-*.rpm

Other external packages that are needed for dependencies, HA, DRBD, etc
can be found at the external_packages folder.

In order to build a version from source, just run:
$ make rpm

Usage:
------
For further information on how to use vsa and for commands references
see the README and release_notes files.

Contact Info:
-------------
for any Questions you may have please contact us at: Openstack@mellanox.com
