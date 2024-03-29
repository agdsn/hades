# syntax=docker/dockerfile:1
FROM debian:bullseye
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>
ENV LANG=C.UTF-8 container=docker
COPY etc/ /etc/

RUN --mount=type=cache,target=/var/cache/apt --mount=type=cache,target=/var/lib/apt \
    export DEBIAN_FRONTEND="noninteractive" \
    && rm -f /etc/apt/apt.conf.d/docker-clean \
    && echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache \
    && apt-get update \
    && apt-get install -y \
    aptitude \
    bandit \
    bash-completion \
    bats \
    black \
    bridge-utils \
    build-essential \
    curl \
    dbus \
    dctrl-tools \
    debian-goodies \
    devscripts \
    dh-exec \
    dh-python \
    dh-virtualenv \
    dhcpcd5 \
    dns-root-data \
    dnsmasq \
    dnsutils \
    elfutils \
    equivs \
    fakeroot \
    flake8 \
    freeradius \
    freeradius-postgresql \
    freeradius-utils \
    gdb \
    gdebi-core \
    git \
    git-buildpackage \
    ifupdown \
    ipset \
    iptables \
    iputils-ping \
    isc-dhcp-relay \
    isort \
    keepalived \
    less \
    libxml2-utils \
    lintian \
    mypy \
    nginx \
    packaging-dev \
    piuparts \
    policykit-1 \
    postgresql \
    postgresql-contrib \
    pycodestyle \
    pydocstyle \
    pyflakes3 \
    pylama \
    pylint \
    pypy3 \
    pypy3-dev \
    python3-all \
    python3-all-dev \
    python3-babel \
    python3-cairo \
    python3-celery \
    python3-flask \
    python3-flask-babel \
    python3-gi \
    python3-guzzle-sphinx-theme \
    python3-jinja2 \
    python3-kombu \
    python3-nacl \
    python3-netaddr \
    python3-pip \
    python3-psycopg2 \
    python3-pydbus \
    python3-pyrad \
    python3-pyroute2 \
    python3-pysnmp4 \
    python3-pytest \
    python3-pytest-mock \
    python3-setuptools \
    python3-sphinx \
    python3-sphinx-argparse \
    python3-sphinx-autodoc-typehints \
    python3-sqlalchemy \
    python3-systemd \
    python3-venv \
    rabbitmq-server \
    radon \
    reprotest \
    shellcheck \
    socat \
    strace \
    sudo \
    systemd \
    systemd-coredump \
    tcpdump \
    tmux \
    unbound \
    unzip \
    uwsgi \
    uwsgi-plugin-python3 \
    vim-nox \
    zsh \
    && curl -L \
    'https://git.grml.org/f/grml-etc-core/etc/zsh/zshrc' -o /etc/zsh/zshrc \
    'https://git.grml.org/f/grml-etc-core/etc/skel/.zshrc' -o /etc/skel/.zshrc \
    && true

RUN find -L /etc/systemd/system /lib/systemd/system -type f -path '*.wants/*' \
        ! -name '*dbus*' \
        ! -name '*journal*' \
        ! -name '*tmpfiles*' \
        ! -name rabbitmq-server.service \
        ! -name remount-proc-sys.service \
        ! -name remount-sys.service \
        ! -name systemd-logind.service \
        -printf '%f\0' | sort --unique --zero-terminated | xargs --null --no-run-if-empty --verbose systemctl mask \
    && find -L /etc/init.d -type f -perm /u+x,g+x,o+x ! -name rc ! -name rcS -printf '%f\0' | xargs --null --no-run-if-empty --max-args=1 -I'{}' --verbose update-rc.d -f '{}' remove \
    && sed -i -re 's/^#?(ForwardTo[^=]+)=.*$/\1=no/' /etc/systemd/journald.conf

COPY ["build.sh", "entrypoint.sh", "/usr/local/bin/"]

VOLUME [ "/build", "/build/hades"]

STOPSIGNAL SIGRTMIN+3

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["/lib/systemd/systemd", "--system"]
