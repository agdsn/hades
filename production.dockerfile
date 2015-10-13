FROM hades-base
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>

COPY src /build/
RUN cd /build && python3 setup.py install && python3 setup.py clean
ENTRYPOINT ["/usr/local/bin/hades"]
