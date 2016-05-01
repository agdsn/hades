FROM debian:jessie
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>

# An undocumented variable named PGCLUSTER is apparently interpreted by newer
# versions of psql, therefore we introduce an underscore
ENV LANG=C.UTF-8 PGVERSION=9.4
COPY docker/etc/apt/ /etc/apt/

RUN apt-get update && apt-get install \
    build-essential \
    curl \
    dns-root-data \
    dnsmasq \
    freeradius \
    freeradius-postgresql \
    freeradius-utils \
    git \
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

COPY docker/rights.sh docker/mysql_fdw.sh /build/
RUN /build/rights.sh && COMMIT=4226fd573d5d602f5b58f542c0bbd15514559235 /build/mysql_fdw.sh
