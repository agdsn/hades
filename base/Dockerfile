FROM debian:jessie
MAINTAINER Sebastian Schrader <sebastian.schrader@agdsn.de>

# Setup package installation
COPY sources.list /etc/apt/sources.list

# Configure timezone
RUN echo 'Europe/Berlin' > /etc/timezone && dpkg-reconfigure -f noninteractive tzdata

# Configure locale
RUN DEBIAN_FRONTEND=noninteractive DEBIAN_NONINTERACTIVE_SEEN=true apt-get update && \
    apt-get -y install locales && \
    sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/g' /etc/locale.gen && \
    locale-gen && \
    update-locale LANG=en_US.UTF-8

# Upgrade system
RUN apt-get update && apt-get -y upgrade

