readonly EX_OK=0
readonly EX_USAGE=64

msg() {
	echo "$@"
}

error() {
	msg "$@" >&2
}

load_config() {
	local CONFIG
	if ! CONFIG="$(python3 -m hades.bin.export_options --format=bash)"; then
		error "error: could not load config"
		return 2
	fi
	source /dev/stdin <<<"$CONFIG"
}
