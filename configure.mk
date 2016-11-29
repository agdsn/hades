#!/usr/bin/make -f
# --------- #
# Functions #
# --------- #

# find_program(NAMES, [PATH])
# -------------------------------------
# Find the full path of a program. A specific PATH may be specified optionally.
define find_program
$(shell
    $(if $2,PATH="$2";,)
    IFS=':';
    for path in $$PATH; do
        IFS=;
        for exec in $1; do
            if [ -x "$${path}/$${exec}" ]; then
                printf "%s/%s" "$$path" "$$exec";
            exit 0;
            fi;
        done;
    done;
    exit 127
)
endef

# require_program(VARIABLE, NAMES, [PATH])
# ----------------------------------------
# Find the full path of program and store the full path in a given variable.
# Abort if the program can not be found. A specific PATH may be specified
# optionally.
define require_program
$(eval
$1 := $$(call find_program,$2,$3)
ifeq "$$(strip $$($1))" ""
    $$(error Could not find $2)
else
    $$(info Found $2 at $$($1))
endif
)
endef


# -------- #
# Metadata #
# -------- #

PACKAGE_NAME         := hades
PACKAGE_VERSION      := 0.2.0.dev0
PACKAGE_AUTHOR       := Sebastian Schrader
PACKAGE_AUTHOR_EMAIL := sebastian.schrader@agdsn.de
PACKAGE_LICENSE      := MIT
PACKAGE_URL          := http://github.com/agdsn/hades

# ----------- #
# Directories #
# ----------- #

# GNU Coding Standards directories
prefix         = /usr/local
exec_prefix    = $(prefix)
bindir         = $(exec_prefix)/bin
sbindir        = $(exec_prefix)/sbin
libexecdir     = $(exec_prefix)/libexec
datarootdir    = $(prefix)/share
datadir        = $(datarootdir)
sysconfdir     = $(prefix)/etc
sharedstatedir = $(prefix)/com
localstatedir  = $(prefix)/var
runstatedir    = $(localstatedir)/run
includedir     = $(prefix)/include
docdir         = $(datarootdir)/doc/$(PACKAGE_NAME)
infodir        = $(datarootdir)/info
htmldir        = $(docdir)
dvidir         = $(docdir)
pdfdir         = $(docdir)
psdir          = $(docdir)
libdir         = $(exec_prefix)/lib
lispdir        = $(datarootdir)/emacs/site-lisp
localedir      = $(datarootdir)/locale
mandir         = $(datarootdir)/man

# Automake-style package directories
pkglibexecdir    = $(libexecdir)/$(PACKAGE_NAME)
pkgsysconfdir    = $(sysconfdir)/$(PACKAGE_NAME)
pkglocalstatedir = $(localstatedir)/$(PACKAGE_NAME)
pkgrunstatedir   = $(runstatedir)/$(PACKAGE_NAME)
pkglibdir        = $(libdir)/$(PACKAGE_NAME)
pkgdatadir       = $(datadir)/$(PACKAGE_NAME)

# Additional directories
assetdir       = $(pkgdatadir)/assests
dbusconfdir    = $(sysconfdir)/dbus-1/system.d
systemdenvdir  = /etc/default
systemdunitdir = /usr/lib/systemd/system
templatedir    = $(pkgdatadir)/templates
tmpfilesddir   = $(sysconfdir)/tmpfiles.d
venvdir        = $(pkglibdir)

# -------- #
# Programs #
# -------- #

$(call require_program,SHELL,bash)

# Runtime programs
$(call require_program,DNSMASQ,dnsmasq)
$(call require_program,IP,ip)
$(call require_program,IPSET,ipset)
$(call require_program,IPTABLES,iptables)
$(call require_program,IPTABLES_RESTORE,iptables-restore)
$(call require_program,KEEPALIVED,keepalived)
$(call require_program,KILL,kill)
$(call require_program,PG_CONFIG,pg_config)
$(call require_program,PSQL,psql)
$(call require_program,PYTHON3,python3)
$(call require_program,RADIUSD,radiusd freeradius)
$(call require_program,RM,rm)
$(call require_program,SED,sed)
$(call require_program,SYSCTL,sysctl)
$(call require_program,UNBOUND,unbound)
$(call require_program,UNBOUND_ANCHOR,unbound-anchor)
$(call require_program,UNBOUND_CHECKCONF,unbound-checkconf)
$(call require_program,UNBOUND_CONTROL,unbound-control)

pgbindir := $(shell $(PG_CONFIG) --bindir)

$(call require_program,CREATEDB,createdb,$(pgbindir))
$(call require_program,CREATEUSER,createuser,$(pgbindir))
$(call require_program,PG_CTL,pg_ctl,$(pgbindir))
$(call require_program,POSTGRES,postgres,$(pgbindir))

# User and group settings
SYSTEM_GROUP     := hades
AGENT_USER       := hades-agent
AGENT_GROUP      := hades-agent
AGENT_HOME       := $(pkglocalstatedir)/agent
AUTH_DHCP_USER   := hades-auth-dhcp
AUTH_DHCP_GROUP  := hades-auth-dhcp
AUTH_DHCP_HOME   := $(pkglocalstatedir)/auth-dhcp
AUTH_DNS_USER    := hades-auth-dns
AUTH_DNS_GROUP   := hades-auth-dns
AUTH_DNS_HOME    := $(pkglocalstatedir)/auth-dns
DATABASE_USER    := hades-database
DATABASE_GROUP   := hades-database
DATABASE_HOME    := $(pkglocalstatedir)/database
PORTAL_USER      := hades-portal
PORTAL_GROUP     := hades-portal
PORTAL_HOME      := $(pkglocalstatedir)/portal
RADIUS_USER      := hades-radius
RADIUS_GROUP     := hades-radius
RADIUS_HOME      := $(pkglocalstatedir)/radius
UNAUTH_DNS_USER  := hades-unauth
UNAUTH_DNS_GROUP := hades-unauth
UNAUTH_DNS_HOME  := $(pkglocalstatedir)/unauth-dns

NULL :=

# Disable make's built-in suffix rules
.SUFFIXES:

# The following variables are substituted in .in files and are cached in
# cache.mk for subsequent make runs.
SUBSTITUTIONS = \
    PACKAGE_NAME \
    PACKAGE_VERSION \
    PACKAGE_AUTHOR \
    PACKAGE_AUTHOR_EMAIL \
    PACKAGE_LICENSE \
    PACKAGE_URL \
    prefix \
    exec_prefix \
    bindir \
    sbindir \
    libexecdir \
    datarootdir \
    datadir \
    sysconfdir \
    sharedstatedir \
    localstatedir \
    runstatedir \
    includedir \
    docdir \
    infodir \
    htmldir \
    dvidir \
    pdfdir \
    psdir \
    libdir \
    lispdir \
    localedir \
    mandir \
    pkglibexecdir \
    pkgsysconfdir \
    pkglocalstatedir \
    pkgrunstatedir \
    pkglibdir \
    pkgdatadir \
    assetdir \
    dbusconfdir \
    systemdenvdir \
    systemdunitdir \
    templatedir \
    tmpfilesddir \
    venvdir \
    pgbindir \
    SYSTEM_GROUP \
    DNSMASQ \
    IP \
    IPSET \
    IPTABLES \
    IPTABLES_RESTORE \
    KEEPALIVED \
    KILL \
    RADIUSD \
    RM \
    SED \
    SYSCTL \
    UNBOUND \
    UNBOUND_ANCHOR \
    UNBOUND_CHECKCONF \
    UNBOUND_CONTROL \
    PGBINDIR \
    CREATEDB \
    CREATEUSER \
    PG_CONFIG \
    PG_CTL \
    POSTGRES \
    PSQL \
    AGENT_USER \
    AGENT_GROUP \
    AGENT_HOME \
    AUTH_DHCP_USER \
    AUTH_DHCP_GROUP \
    AUTH_DHCP_HOME \
    AUTH_DNS_USER \
    AUTH_DNS_GROUP \
    AUTH_DNS_HOME \
    DATABASE_USER \
    DATABASE_GROUP \
    DATABASE_HOME \
    PORTAL_USER \
    PORTAL_GROUP \
    PORTAL_HOME \
    RADIUS_USER \
    RADIUS_GROUP \
    RADIUS_HOME \
    UNAUTH_DNS_USER \
    UNAUTH_DNS_GROUP \
    UNAUTH_DNS_HOME \
    $(NULL)

CONFIGURE_FILES = \
    bower.json \
    init/dbus/de.agdsn.hades.conf \
    init/tmpfiles.d/hades.conf \
    init/units/hades-agent.service \
    init/units/hades-auth-dhcp.service \
    init/units/hades-auth-dns.service \
    init/units/hades-auth-vrrp.service \
    init/units/hades-cleanup.service \
    init/units/hades-database.service \
    init/units/hades-network.service \
    init/units/hades-radius.service \
    init/units/hades-radius-vrrp.service \
    init/units/hades-refresh.service \
    init/units/hades-unauth-dns.service \
    init/units/hades-unauth-http.service \
    init/units/hades-unauth-portal.service \
    init/units/hades-unauth-vrrp.service \
    scripts/control-database.sh \
    scripts/control-network.sh \
    scripts/functions.sh \
    scripts/package-setup.sh \
    scripts/update-trust-anchor.sh \
    setup.py \
    $(NULL)

all: $(CONFIGURE_FILES) src/hades/constants.py

$(CONFIGURE_FILES): %: %.in configure.mk .FORCE
	@echo Configuring $@
	@$(SED) $(foreach var,$(SUBSTITUTIONS),-e 's|@$(var)@|$($(var))|g' ) < $< > $@
	@chmod --reference=$< $@

src/hades/constants.py: configure.mk .FORCE
	@echo Creating $@
	@printf '%s = "%s"\n' $(foreach var,$(SUBSTITUTIONS),'$(var)' '$($(var))') > $@

clean:
	$(RM) $(CONFIGURE_FILES)
	$(RM) src/hades/constants.py

.FORCE:

.PHONY: all clean .FORCE
