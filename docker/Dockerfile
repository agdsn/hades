FROM debian:jessie
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>
ARG BUILDER_UID=1000
ARG BUILDER_GID=1000
ENV LANG=C.UTF-8 container=docker
COPY etc/ /etc/

RUN apt-get update && apt-get install -y -t jessie-backports \
    bats \
    bridge-utils \
    build-essential \
    curl \
    dbus \
    devscripts \
    dh-exec \
    dh-virtualenv \
    dig \
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
    npm \
    packaging-dev \
    postgresql-9.4 \
    postgresql-contrib-9.4 \
    postgresql-server-dev-9.4 \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-venv \
    sudo \
    tcpdump \
    unbound \
    unzip \
    uwsgi \
    uwsgi-plugin-python3 \
    vim-nox \
    && apt-get clean \
    && pg_lsclusters -h | cut -d ' ' -f 1-2 | xargs -rn 2 pg_dropcluster \
    && ln -s /usr/bin/nodejs /usr/bin/node \
    && find /etc/systemd/system /lib/systemd/system -path '*.wants/*' ! -name '*journal*' ! -name '*tmpfiles*' ! -name '*dbus*' -delete \
    && find /etc/rc*.d -type l -delete \
    && adduser --system --home /build --shell /bin/bash --uid $BUILDER_UID --gid $BUILDER_GID builder \
    && sed -i -re 's/^#?(ForwardTo[^=]+)=.*$/\1=no/' /etc/systemd/journald.conf

COPY ["build.sh", "/usr/local/bin"]

VOLUME [ "/sys/fs/cgroup", "/build", "/build/hades"]

CMD ["/lib/systemd/systemd", "--system"]
