#!/usr/bin/env bash

set -exuo pipefail
shopt -qs failglob

declare -A PACKAGES=(
	[dh-virtualenv]=dh-virtualenv
	[isc-kea]="kea-common kea-admin kea-dhcp4-server kea-dhcp6-server"
	[postgresql-mysql-fdw]=postgresql-9.4-mysql-fdw
	)
declare -A REPOSITORIES=(
	[dh-virtualenv]=https://github.com/spotify/dh-virtualenv.git
	[isc-kea]=https://github.com/sebschrader/debian-pkg-isc-kea
	[postgresql-mysql-fdw]=https://github.com/sebschrader/debian-pkg-postgresql-mysql-fdw
)

pushd /build

for source_package in "${!PACKAGES[@]}"; do
	echo "Building $source_package"
	if [[ ! -e ${source_package} ]]; then
		git clone "${REPOSITORIES[$source_package]}" ${source_package}
	fi
	mk-build-deps --install --remove -t 'apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends -t jessie-backports' "${source_package}/debian/control"
	pushd "$source_package"
	version="$(dpkg-parsechangelog -S Version)"
	dpkg-buildpackage -uc -us -b
	popd
	for package in ${PACKAGES[$source_package]}; do
		dpkg -i ${package}_${version}_*.deb
	done
	apt-get purge "${source_package}-build-deps"
	apt-get autoremove --purge
done
