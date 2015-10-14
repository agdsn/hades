FROM debian:jessie
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>

# An undocumented variable named PGCLUSTER is apparently interpreted by newer
# versions of psql, therefore we introduce an underscore
ENV LANG=C.UTF-8 PG_VERSION=9.4 PG_CLUSTER=main
COPY docker/etc/apt/ /etc/apt/

RUN apt-get update && apt-get install \
    dns-root-data \
    dnsmasq \
    freeradius \
    freeradius-postgresql \
    git \
    iptables \
    keepalived \
    libmysqlclient-dev \
    nginx \
    npm \
    python3-pip \
    postgresql \
    postgresql-server-dev-${PG_VERSION} \
    python3-babel \
    python3-celery \
    python3-dev \
    python3-flask \
    python3-jinja2 \
    python3-netaddr \
    python3-psycopg2 \
    python3-setuptools \
    python3-sqlalchemy \
    python3-sqlalchemy-ext \
    unbound \
    uwsgi \
    uwsgi-plugin-python3 \
    curl \
    build-essential \
    unzip \
    && apt-get clean \
    && ln -s /usr/bin/nodejs /usr/bin/node \
    && npm install -g bower \
    && pip3 install \
    Flask-Babel \
    pyroute2 \
    && npm install -g bower \
    && \
    pg_dropcluster ${PG_VERSION} ${PG_CLUSTER} && \
    pg_createcluster --locale C -e UTF-8 ${PG_VERSION} ${PG_CLUSTER}

COPY docker/rights.sh docker/mysql_fdw.sh /build/
RUN cd /build && \
    /build/rights.sh && \
    /build/mysql_fdw.sh
