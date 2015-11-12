#!/bin/bash
set -euo pipefail

download_from_pgxn() {
	curl --silent --show-error -O -L http://api.pgxn.org/dist/mysql_fdw/${VERSION}/mysql_fdw-${VERSION}.zip
	sha512sum --status --strict --check <<-HASH
	${SHA512} *mysql_fdw-${VERSION}.zip
HASH
	unzip mysql_fdw-${VERSION}.zip
	mv mysql_fdw-${VERSION} mysql_fdw
}

download_from_git() {
	git clone -q https://github.com/EnterpriseDB/mysql_fdw/ mysql_fdw
	git -C mysql_fdw checkout -q ${COMMIT}
}

download() {
    if [[ -n "${VERSION:-}" && -n "${SHA512:-}" ]]; then
        download_from_pgxn
    elif [[ -n "${COMMIT:-}" ]]; then
        download_from_git
    else
        echo "You must specify either VERSION and SHA512 or COMMIT" >&2
        exit 1
    fi
}

build() {
	make -C mysql_fdw USE_PGXS=1
}

install() {
	make -C mysql_fdw USE_PGXS=1 install
}

clean() {
	rm -rf mysql_fdw*
}

download
build
install
clean
