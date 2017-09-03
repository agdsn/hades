FROM debian:stretch
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>
ARG BUILDER_UID=1000
ARG BUILDER_GID=1000
ENV LANG=C.UTF-8 container=docker
COPY etc/ /etc/

RUN export DEBIAN_FRONTEND="noninteractive" && \
    apt-get update && apt-get install -y \
    bash-completion \
    bats \
    bridge-utils \
    build-essential \
    curl \
    dbus \
    devscripts \
    dhcpcd5 \
    dh-exec \
    dh-virtualenv \
    dns-root-data \
    dnsmasq \
    dnsutils \
    equivs \
    fakeroot \
    freeradius \
    freeradius-postgresql \
    freeradius-utils \
    gdb \
    git \
    git-buildpackage \
    ipset \
    iptables \
    isc-dhcp-relay \
    keepalived \
    less \
    libxml2-utils \
    lintian \
    nginx \
    packaging-dev \
    policykit-1 \
    postgresql-9.6 \
    postgresql-contrib-9.6 \
    postgresql-server-dev-9.6 \
    pypy \
    pypy-dev \
    pypy-ipaddress \
    pypy-pytest \
    pypy-setuptools \
    python-all \
    python-all-dev \
    python-ipaddr \
    python-ipaddress \
    python-mock \
    python-netaddr \
    python-pytest \
    python-pytest-runner \
    python-setuptools \
    python3-all \
    python3-all-dev \
    python3-babel \
    python3-celery \
    python3-flask \
    python3-flask-babel \
    python3-gi \
    python3-jinja2 \
    python3-netaddr \
    python3-pip \
    python3-psycopg2 \
    python3-pydbus \
    python3-pyrad \
    python3-pyroute2 \
    python3-pysnmp4 \
    python3-pytest \
    python3-pytest-runner \
    python3-sqlalchemy \
    python3-setuptools \
    python3-venv \
    rabbitmq-server \
    sudo \
    systemd \
    systemd-coredump \
    tcpdump \
    unbound \
    unzip \
    uwsgi \
    uwsgi-plugin-python3 \
    vim-nox \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pg_lsclusters --no-header | cut -d ' ' -f 1-2 | xargs --no-run-if-empty --max-args=2 pg_dropcluster \
    && find -L /etc/systemd/system /lib/systemd/system -type f -path '*.wants/*' \
        ! -name '*dbus*' \
        ! -name '*journal*' \
        ! -name '*tmpfiles*' \
        ! -name rabbitmq-server.service \
        ! -name remount-proc-sys.service \
        ! -name remount-sys.service \
        ! -name systemd-logind.service \
        -printf '%f\0' | sort --unique --zero-terminated | xargs --null --no-run-if-empty systemctl mask \
    && find -L /etc/init.d -type f -perm /u+x,g+x,o+x ! -name rc ! -name rcS -printf '%f\0' | xargs --null --no-run-if-empty --max-args=1 sh -c 'update-rc.d -f "$1" remove' sh \
    && adduser --system --home /build --shell /bin/bash --uid $BUILDER_UID builder \
    && sed -i -re 's/^#?(ForwardTo[^=]+)=.*$/\1=no/' /etc/systemd/journald.conf

COPY ["build.sh", "/usr/local/bin"]

VOLUME [ "/sys/fs/cgroup", "/build", "/build/hades"]

STOPSIGNAL SIGRTMIN+3

CMD ["/lib/systemd/systemd", "--system"]
