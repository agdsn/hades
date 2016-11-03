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
    libmysqlclient-dev \
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
    unbound \
    unzip \
    uwsgi \
    uwsgi-plugin-python3 \
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

COPY docker/mysql_fdw.sh /build/
RUN VERSION=2.1.2 \
    SHA512=3da432c008025518b9fa71aa1b4cd35ad1850b192b6cedecd963a5347dc9f6fc005c45ab6c21329f2617a2a2edab841b44ac310ae7b3490a16e0d71ca896efbe \
    /build/mysql_fdw.sh
