FROM debian
MAINTAINER Stefan Haller <stefan.haller@tu-dresden.de>

COPY docker/etc/apt/sources.list /etc/apt/sources.list
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    dnsutils \
    dhcpcd5 \
    vim-tiny

CMD ["bash", "-l"]
