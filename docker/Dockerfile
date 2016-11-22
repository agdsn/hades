FROM debian:jessie
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>

ENV LANG=C.UTF-8 container=docker
COPY etc/apt/ /etc/apt/

RUN apt-get update && apt-get install -y -t jessie-backports \
    bridge-utils \
    build-essential \
    curl \
    dbus \
    devscripts \
    dh-virtualenv \
    dnsutils \
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
    tcpdump \
    unbound \
    unzip \
    uwsgi \
    uwsgi-plugin-python3 \
    vim-nox \
    && apt-get clean \
    && pg_lsclusters -h | cut -d ' ' -f 1-2 | xargs -rn 2 pg_dropcluster \
    && ln -s /usr/bin/nodejs /usr/bin/node \
    && npm install -g bower \
    && find /etc/systemd/system /lib/systemd/system -path '*.wants/*' ! -name '*journal*' ! -name '*tmpfiles*' ! -name '*dbus*' -delete \
    && find /etc/rc*.d -type l -delete \
    && sed -i -re 's/^#?(ForwardTo[^=]+)=.*$/\1=no/' /etc/systemd/journald.conf

COPY ["build.sh", "/usr/local/bin"]

VOLUME [ "/sys/fs/cgroup", "/build", "/build/hades"]

CMD ["/lib/systemd/systemd", "--system"]
