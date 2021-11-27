#!/usr/bin/env bash

set -euo pipefail
shopt -qs failglob

readonly SOURCE_DIR="/build/hades"
readonly -A PACKAGES=(
	[arpreq]="${SOURCE_DIR}/vendor/arpreq"
	[hades]="${SOURCE_DIR}"
)

for package in "${!PACKAGES[@]}"; do
	echo "Building ${package} package ..."
	(set -x; cd "${PACKAGES[${package}]}" && dpkg-buildpackage --no-sign -b)
done
