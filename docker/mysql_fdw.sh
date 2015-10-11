#!/bin/bash
set -euo pipefail
readonly VERSION=2.0.1
readonly SHA512=4201bb82357cea6b4f8415d4f2095652c2015d3bc436978cdb8b46fdb6d2288e7fbb9e28d4bd09a8b9c48bbce396e4655454d085cb3049ad42a1889353a05238

curl -O -L http://api.pgxn.org/dist/mysql_fdw/${VERSION}/mysql_fdw-${VERSION}.zip
sha512sum --status --strict --check <<HASH
${SHA512} *mysql_fdw-${VERSION}.zip
HASH
unzip mysql_fdw-${VERSION}.zip
make -C mysql_fdw-${VERSION} USE_PGXS=1
make -C mysql_fdw-${VERSION} USE_PGXS=1 install
rm -rf mysql_fdw-${VERSION} mysql_fdw-${VERSION}.zip
