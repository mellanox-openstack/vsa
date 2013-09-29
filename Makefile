#
# Copyright (C) 2012 Roi Dayan <roid@mellanox.com>
#

all: rpm

RPMTOP=$(shell bash -c "pwd -P")/rpmtop
SPEC=vsa.spec
_lastrelease=$(shell git describe --tags | cut -d- -f3 | tr -d '[a-zA-Z_]')
_hash=$(shell git rev-parse HEAD | cut -c 1-6)
_branch=$(shell git branch | grep '^*' | sed 's/^..\(.*\)/\1/' |\
		sed 's/[^a-zA-Z0-9_.]//g')
_brtmp=$(shell echo $(_branch) | cut -c 1-3)

ifeq ($(_brtmp),vsa)
	_version=$(shell echo $(_branch) | cut -d- -f2)
	_release=$(_lastrelease)
else
	_version=git
	_release=$(_hash)
endif

_dir=vsa-$(_version)-$(_release)
TARBALL=$(_dir).tgz
SRPM=$(RPMTOP)/SRPMS/$(_dir).src.rpm

.PHONY: top
top:
	mkdir -p $(RPMTOP)/{RPMS,SRPMS,SOURCES,BUILD,SPECS,tmp}

.PHONY: tarball
tarball: top
	mkdir -p $(RPMTOP)/tmp/$(_dir)
	cp -a src $(RPMTOP)/tmp/$(_dir)
	cp -a etc $(RPMTOP)/tmp/$(_dir)
	cp -a sbin $(RPMTOP)/tmp/$(_dir)
	tar -czf $(RPMTOP)/SOURCES/$(TARBALL) -C $(RPMTOP)/tmp $(_dir)

.PHONY: srpm
srpm: tarball
	sed 's/^%define version .*/%define version $(_version)/;s/^%define rel .*/%define rel $(_release)/' $(SPEC) > $(RPMTOP)/SPECS/$(SPEC)
	rpmbuild -bs --define="_topdir $(RPMTOP)" $(RPMTOP)/SPECS/$(SPEC)

.PHONY: rpm
rpm: srpm
	rpmbuild -bb --define="_topdir $(RPMTOP)" $(RPMTOP)/SPECS/$(SPEC)

clean:
	rm -fr $(RPMTOP)
