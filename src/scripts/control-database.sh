#!/usr/bin/env bash
set -euo pipefail

source /usr/local/bin/functions.sh

print_usage() {
	msg "\
Usage: $0 [-h] [--help] { start | stop | reload | clear }

Control the hades database PostgreSQL cluster.

Commands:
  init                  Initialize the database
  start                 Start the database
  stop                  Stop the database
  reload                Reload the database
  clear                 Clear the database

Options
  -h --help             Print this message
  --clear               Delete existing cluster before"
}

clear_pgdata() {
	msg "Removing PostgreSQL cluster at $PGDATA"
	shopt -s dotglob
	rm -rf "$PGDATA"/*
	shopt -u dotglob
}

cleanup() {
	error "Aborting database initialisation"
	pg_ctl stop -s || true
	clear_pgdata
}

cluster_exists() {
	[[ -f "$PGDATA/PG_VERSION" && -d "$PGDATA/base" ]]
}

check_cluster_version() {
	local CLUSTER_VERSION=
	read -r CLUSTER_VERSION < "$PGDATA/PG_VERSION" || :
	local PG_VERSION="$(postgres --version | sed 's/.* \([0-9]\+\.[0-9]\+\).[0-9]\+/\1/')"
	if [[ "$PG_VERSION" != "$CLUSTER_VERSION" ]]; then
		error "Error: version of PostgreSQL cluster located at $PGDATA ($CLUSTER_VERSION) does not match version of postgres executable ($PG_VERSION)"
	fi
}

generate_config() {
	python3 -m hades.bin.generate_config postgresql /run/hades/database
}

do_init() {
	if cluster_exists; then
		check_cluster_version
		msg "Skipping database initialisation. PostgreSQL cluster already exists."
		return "$EX_OK"
	fi

	trap cleanup EXIT HUP INT QUIT ABRT
	msg "Initialising new PostgreSQL cluster at $PGDATA"
	pg_ctl initdb -s -o "--auth-host=password --auth-local=peer --encoding=UTF-8 --locale=C"
	rm "$PGDATA"/postgresql.conf "$PGDATA"/pg_hba.conf "$PGDATA"/pg_ident.conf
	generate_config
	pg_ctl start -w -s -o '-c config_file=/run/hades/database/postgresql.conf'
	for user in "$HADES_RADIUS_USER" "$HADES_AGENT_USER" "$HADES_PORTAL_USER"; do
		createuser "$user"
	done

	if [[ -n "$HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE" ]]; then
		msg "Creating local foreign database '$HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE' for testing."
		createdb "$HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE"
		psql --quiet --set=ON_ERROR_STOP=1 --no-psqlrc --single-transaction <<-COMMAND
			CREATE ROLE "$HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE" WITH LOGIN INHERIT UNENCRYPTED PASSWORD '$HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE';
			COMMAND
		msg "Loading local foreign database schema"
		python3 -m hades.bin.generate_config schema_fdw.sql.j2 | psql --quiet --set=ON_ERROR_STOP=1 --no-psqlrc --single-transaction --file=- "$HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE"
	fi

	msg "Creating database '$HADES_POSTGRESQL_DATABASE'"
	createdb "$HADES_POSTGRESQL_DATABASE"
	msg "Loading database schema"
	python3 -m hades.bin.generate_config schema.sql.j2 | psql --quiet --set=ON_ERROR_STOP=1 --no-psqlrc --single-transaction --file=- "$HADES_POSTGRESQL_DATABASE"
	pg_ctl stop -s
	msg "PostgreSQL cluster at $PGDATA successfully initialised."
	trap - EXIT HUP INT QUIT ABRT
	return "$EX_OK"
}

do_start() {
	if pg_ctl status &>/dev/null; then
		error "Error: PostgreSQL cluster already running"
		return 3
	fi
	if cluster_exists; then
		check_cluster_version
	else
		error "Error: PostgreSQL cluster at $PGDATA does not exists"
		return 2
	fi
	generate_config
	pg_ctl start -s -w -t 30 -o '-c config_file=/run/hades/database/postgresql.conf'
}

do_stop() {
	pg_ctl stop -s -t 30 -m fast
}

do_reload() {
	generate_config
	pg_ctl reload -s
}

do_clear() {
	if pg_ctl status &>/dev/null; then
		error "Error: can't clear running PostgreSQL cluster"
		return 3
	fi
	clear_pgdata
}

main() {
	if (( $# != 1)); then
		print_usage
		exit "$EX_USAGE"
	fi
	case "$1" in
		-h|--help|help)
			print_usage
			exit "$EX_OK"
			;;
		init|start|stop|reload|clear)
			load_config
			export PGHOST="$HADES_POSTGRESQL_SOCKET_DIRECTORY"
			export PGPORT="$HADES_POSTGRESQL_PORT"
			export PGDATA=/var/lib/hades/database
			do_$1 "$@"
			;;
		*)
			print_usage
			exit "$EX_USAGE"
			;;
	esac
}

main "$@"
