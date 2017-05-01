FROM debian:stretch
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>
ARG BUILDER_UID=1000
ARG BUILDER_GID=1000
ENV LANG=C.UTF-8 container=docker
COPY etc/ /etc/

RUN apt-get update && apt-get install -y \
    apt-transport-https \
    bats \
    bridge-utils \
    build-essential \
    curl \
    dbus \
    devscripts \
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
    git \
    git-buildpackage \
    ipset \
    iptables \
    keepalived \
    less \
    lintian \
    nginx \
    packaging-dev \
    policykit-1 \
    postgresql-9.6 \
    postgresql-contrib-9.6 \
    postgresql-server-dev-9.6 \
    python3-dev \
    python3-gi \
    python3-pip \
    python3-setuptools \
    python3-venv \
    rabbitmq-server \
    software-properties-common \
    sudo \
    systemd \
    tcpdump \
    unbound \
    unzip \
    uwsgi \
    uwsgi-plugin-python3 \
    vim-nox \
    && apt-key add /etc/apt/nodesource.gpg.key \
    && printf '%s\n' 'deb https://deb.nodesource.com/node_6.x jessie main' > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pg_lsclusters --no-header | cut -d ' ' -f 1-2 | xargs --no-run-if-empty --max-args=2 pg_dropcluster \
    && find -L /etc/systemd/system /lib/systemd/system -type f -path '*.wants/*' ! -name '*journal*' ! -name '*tmpfiles*' ! -name '*dbus*' -printf '%f\0' | sort --unique --zero-terminated | xargs --null --no-run-if-empty systemctl mask \
    && find -L /etc/init.d -type f -perm /u+x,g+x,o+x ! -name rc ! -name rcS -printf '%f\0' | xargs --null --no-run-if-empty --max-args=1 sh -c 'update-rc.d -f "$1" remove' sh \
    && adduser --system --home /build --shell /bin/bash --uid $BUILDER_UID builder \
    && sed -i -re 's/^#?(ForwardTo[^=]+)=.*$/\1=no/' /etc/systemd/journald.conf

COPY ["build.sh", "/usr/local/bin"]

VOLUME [ "/sys/fs/cgroup", "/build", "/build/hades"]

CMD ["/lib/systemd/systemd", "--system"]
