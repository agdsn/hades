#!/bin/bash

set -Eeuo pipefail

readonly home=/build
readonly uid="$(stat --printf '%u' "$home")"
readonly gid="$(stat --printf '%g' "$home")"

if ! getent group builder; then
	addgroup --gid "$gid" builder
fi

if ! getent passwd builder; then
	adduser --home "$home" --no-create-home --shell /bin/zsh --uid "$uid" --gid "$gid" builder
fi

exec "$@"
