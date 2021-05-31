#!/bin/bash
# Alternative dhcpcd-run-hooks(8) script that stores all environment variables

set -euo pipefail

export -n script_output_dir variable

{
	echo "local -A ${variable}"
	env --null | sed --null-data -n -E -e 's#([^=]*)=(.*)#\1\x00\2#p' | xargs --null --no-run-if-empty bash -c "printf '${variable}[%s]=%q\n' "'"$@"' bash
} > "${script_output_dir}/${reason}"
