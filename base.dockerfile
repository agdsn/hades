FROM debian:jessie
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>

ENV LANG=C.UTF-8 PGVERSION=9.4 container=docker
COPY docker/etc/apt/ /etc/apt/

RUN apt-get update && apt-get install -y -t jessie-backports \
    build-essential \
    bridge-utils \
    curl \
    dns-root-data \
    dnsmasq \
    dnsutils \
    freeradius \
    freeradius-postgresql \
    freeradius-utils \
    git \
    ipset \
    iptables \
    keepalived \
    less \
    libmysqlclient-dev \
    nginx \
    npm \
    postgresql \
    postgresql-contrib \
    postgresql-server-dev-${PGVERSION} \
    python3-babel \
    python3-celery \
    python3-dev \
    python3-flask \
    python3-jinja2 \
    python3-netaddr \
    python3-pip \
    python3-psycopg2 \
    python3-setuptools \
    python3-sqlalchemy \
    python3-sqlalchemy-ext \
    unbound \
    unzip \
    uwsgi \
    uwsgi-plugin-python3 \
    && apt-get clean \
    && ln -s /usr/bin/nodejs /usr/bin/node \
    && npm install -g bower \
    && pip3 install \
    Flask-Babel \
    pyroute2 \
    && npm install -g bower \
    && pg_dropcluster ${PGVERSION} main

RUN echo "LANG=$LANG" >/etc/locale.conf

COPY docker/rights.sh docker/mysql_fdw.sh /build/
RUN /build/rights.sh \
    && VERSION=2.1.2 \
       SHA512=3da432c008025518b9fa71aa1b4cd35ad1850b192b6cedecd963a5347dc9f6fc005c45ab6c21329f2617a2a2edab841b44ac310ae7b3490a16e0d71ca896efbe \
       /build/mysql_fdw.sh
