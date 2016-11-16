FROM debian:jessie
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>

ENV LANG=C.UTF-8 container=docker
COPY etc/apt/ /etc/apt/

RUN apt-get update && apt-get install -y -t jessie-backports \
    build-essential \
    bridge-utils \
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
    postgresql \
    postgresql-contrib \
    postgresql-server-dev-all \
    packaging-dev \
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
    && npm install -g bower

COPY requirements.txt /opt/hades/requirements.txt
RUN pyvenv /opt/hades \
    && . /opt/hades/bin/activate \
    && pip install --upgrade pip setuptools \
    && pip install -r /opt/hades/requirements.txt

RUN echo "LANG=$LANG" >/etc/locale.conf

