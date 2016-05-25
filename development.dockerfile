FROM hades-base
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>

# Install some development tools.
RUN apt-get install -y vim-nox tcpdump dnsutils && apt-get clean

# Delete unwanted systemd units and disable journal forwarding
RUN for i in /etc/systemd /lib/systemd /lib/systemd; do \
        find "$i"/system -path '*.wants/*' -a -not -name '*journal*' -a -not -name '*tmpfiles*' -delete; \
    done \
    && for i in /etc/rc*.d; do \
        find "$i" -type l -name 'S*' -delete; \
    done \
    && sed -i -re 's/^#?(ForwardTo[^=]+)=.*$/\1=no/' /etc/systemd/journald.conf

# Install bower dependencies
COPY src/bower.json /build/
RUN cd /build && bower install --allow-root

# Install hades
COPY src/ /build/
RUN cd /build \
    && python3 setup.py install \
    && python3 setup.py compile_catalog -d hades/portal/translations \
    && python3 setup.py clean \
    && cd / \
    && rm -rf /build/

# Copy hades config to container
COPY configs/example.py /etc/hades/config.py
RUN printf '%s=%s\n' \
        HADES_CONFIG /etc/hades/config.py \
        PGVERSION "$PGVERSION" \
        >/etc/hades/env

# Copy hades systemd units. We do not enable the units, because this makes
# things easier for development: We can start the container, inject all the
# necessary interfaces and only afterwards start the systemd units.
COPY systemd/ /lib/systemd/system
RUN . /etc/hades/env \
    && cd /lib/systemd/system \
    && python3 -m hades.config.generate tmpfiles.conf.j2 /etc/tmpfiles.d/hades.conf

# Setup local radius database used for development
COPY docker/postgres_fdw.sh /build/
RUN chmod 755 /build/postgres_fdw.sh && /build/postgres_fdw.sh && rm -rf /build/

CMD ["/lib/systemd/systemd", "--system"]
