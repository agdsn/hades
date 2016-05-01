#!/bin/bash
set -euo pipefail

. /etc/hades/env
export PATH="/usr/lib/postgresql/${PGVERSION}/bin:${PATH}"
export PGDATA="/var/lib/postgresql/hades"
source <(python3 -m hades.config.export)

# Run as postgres user
if [[ $(id -u) -eq 0 ]]; then
    exec python3 -m hades.common.su "${HADES_POSTGRESQL_USER}" "$0" "$@"
fi

# Let the hades script configure the database cluster. This might use some
# special arguments to pg_ctl initdb.
hades init-database-system

# Create database 'radius' and populate the schema. This enables us to point
# the foreign tables to the local running database instance for development.
pg_ctl start -w -s
createdb radius
python3 -m hades.config.generate schema_fdw.sql.j2 | psql --quiet --set=ON_ERROR_STOP=1 --no-psqlrc --single-transaction --file=- radius
pg_ctl stop -s
