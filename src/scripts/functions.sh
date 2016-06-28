readonly EX_OK=0
readonly EX_USAGE=64

msg() {
	echo "$@"
}

error() {
	msg "$@" >&2
}

load_config() {
	source <(python3 -m hades.config.export --format=bash)
}
