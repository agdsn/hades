FROM debian:jessie
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>
ENV LANG=C.UTF-8
COPY docker/etc/apt/ /etc/apt/

RUN apt-get update && apt-get install \
    arping \
    dnsmasq \
    freeradius \
    freeradius-postgresql \
    libmysqlclient-dev \
    nginx \
    python3-pip \
    postgresql \
    postgresql-server-dev-9.4 \
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
    gcc \
    make \
    unzip \
    && \
    apt-get clean && \
    pip3 install \
    Flask-Babel \
    pyroute2 \
    && \
    pg_dropcluster 9.4 main && \
    pg_createcluster --locale C -e UTF-8 9.4 main

COPY docker/ /build/
RUN cd /build && \
    /build/rights.sh && \
    /build/mysql_fdw.sh

COPY src docker/* /build/
RUN cd /build && python3 setup.py install

ENTRYPOINT ["/build/entrypoint.sh"]
