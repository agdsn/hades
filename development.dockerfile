FROM hades-base
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>

# Install some development tools.
RUN apt-get install -y vim-nox tcpdump dnsutils && apt-get clean

# Delete unwanted systemd units and disable journal forwarding
RUN  find /etc/systemd/system /lib/systemd/system -path '*.wants/*' ! -name '*journal*' ! -name '*tmpfiles*' ! -name '*dbus*' -delete \
    && find /etc/rc*.d -type l -delete \
    && sed -i -re 's/^#?(ForwardTo[^=]+)=.*$/\1=no/' /etc/systemd/journald.conf

# Install bower dependencies
COPY .bowerrc bower.json /build/
RUN cd /build && bower install --allow-root

# Install hades
COPY LICENSE README.md MANIFEST.in setup.py /build/
COPY src/ /build/src/
RUN cd /build && pip3 install .

# Copy hades config to container
COPY configs/example.py /etc/hades/config.py

# Copy hades systemd units. We do not enable the units, because this makes
# things easier for development: We can start the container, inject all the
# necessary interfaces and only afterwards start the systemd units.
COPY docker/users.sh /build/
COPY systemd/ /lib/systemd/system
COPY systemd/hades.default /etc/default/hades
RUN /build/users.sh \
    && python3 -m hades.bin.generate_config tmpfiles.conf.j2 /etc/tmpfiles.d/hades.conf \
    && python3 -m hades.bin.generate_config hades.busconfig.j2 /etc/dbus-1/system.d/hades.conf

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/lib/systemd/systemd", "--system"]
