#!/usr/bin/make -f
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
PREFIX         = /usr/local
EXEC_PREFIX    = $(PREFIX)
BINDIR         = $(EXEC_PREFIX)/bin
SBINDIR        = $(EXEC_PREFIX)/sbin
LIBEXECDIR     = $(EXEC_PREFIX)/libexec
DATAROOTDIR    = $(PREFIX)/share
DATADIR        = $(DATAROOTDIR)
SYSCONFDIR     = $(PREFIX)/etc
SHAREDSTATEDIR = $(PREFIX)/com
LOCALSTATEDIR  = $(PREFIX)/var
RUNSTATEDIR    = $(LOCALSTATEDIR)/run
INCLUDEDIR     = $(PREFIX)/include
DOCDIR         = $(DATAROOTDIR)/doc/$(PACKAGE_NAME)
INFODIR        = $(DATAROOTDIR)/info
HTMLDIR        = $(DOCDIR)
DVIDIR         = $(DOCDIR)
PDFDIR         = $(DOCDIR)
PSDIR          = $(DOCDIR)
LIBDIR         = $(EXEC_PREFIX)/lib
LISPDIR        = $(DATAROOTDIR)/emacs/site-lisp
LOCALEDIR      = $(DATAROOTDIR)/locale
MANDIR         = $(DATAROOTDIR)/man

# Automake-style package directories
PKGLIBEXECDIR    = $(LIBEXECDIR)/$(PACKAGE_NAME)
PKGSYSCONFDIR    = $(SYSCONFDIR)/$(PACKAGE_NAME)
PKGLOCALSTATEDIR = $(LOCALSTATEDIR)/$(PACKAGE_NAME)
PKGRUNSTATEDIR   = $(RUNSTATEDIR)/$(PACKAGE_NAME)
PKGLIBDIR        = $(LIBDIR)/$(PACKAGE_NAME)
PKGDATADIR       = $(DATADIR)/$(PACKAGE_NAME)

# Additional directories
ASSETSDIR      = $(PKGDATADIR)/assests
DBUSCONFDIR    = $(SYSCONFDIR)/dbus-1/system.d
SYSTEMDENVDIR  = /etc/default
SYSTEMDUNITDIR = /usr/lib/systemd/system
TEMPLATEDIR    = $(PKGDATADIR)/templates
TMPFILESDDIR   = $(SYSCONFDIR)/tmpfiles.d
VENVDIR        = $(PKGLIBDIR)

# -------- #
# Programs #
# -------- #

# Find a program on PATH
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

# Find a program and store the full path in a variable
# Abort if the program can not be found
define require_program
$1 := $$(call find_program,$2,$3)
ifeq "$$(strip $$($1))" ""
    $$(error Could not find $2)
else
    $$(info Found $2 at $$($1))
endif
endef

# Runtime programs
$(eval $(call require_program,DNSMASQ,dnsmasq))
$(eval $(call require_program,IP,ip))
$(eval $(call require_program,IPSET,ipset))
$(eval $(call require_program,IPTABLES,iptables))
$(eval $(call require_program,IPTABLES_RESTORE,iptables-restore))
$(eval $(call require_program,KEEPALIVED,keepalived))
$(eval $(call require_program,KILL,kill))
$(eval $(call require_program,PG_CONFIG,pg_config))
$(eval $(call require_program,PSQL,psql))
$(eval $(call require_program,PYTHON3,python3))
$(eval $(call require_program,RADIUSD,radiusd freeradius))
$(eval $(call require_program,RM,rm))
$(eval $(call require_program,SED,sed))
$(eval $(call require_program,SYSCTL,sysctl))
$(eval $(call require_program,UNBOUND,unbound))
$(eval $(call require_program,UNBOUND_CHECKCONF,unbound-checkconf))
$(eval $(call require_program,UNBOUND_CONTROL,unbound-control))

PGBINDIR := $(shell $(PG_CONFIG) --bindir)

$(eval $(call require_program,CREATEDB,createdb,$(PGBINDIR)))
$(eval $(call require_program,CREATEUSER,createuser,$(PGBINDIR)))
$(eval $(call require_program,PG_CTL,pg_ctl,$(PGBINDIR)))
$(eval $(call require_program,POSTGRES,postgres,$(PGBINDIR)))

# User and group settings
SYSTEM_GROUP     := hades
AGENT_USER       := hades-agent
AGENT_GROUP      := hades-agent
AGENT_HOME       := $(PKGLOCALSTATEDIR)/agent
AUTH_DNS_USER    := hades-auth-dns
AUTH_DNS_GROUP   := hades-auth-dns
AUTH_DNS_HOME    := $(PKGLOCALSTATEDIR)/auth-dns
DATABASE_USER    := hades-database
DATABASE_GROUP   := hades-database
DATABASE_HOME    := $(PKGLOCALSTATEDIR)/database
PORTAL_USER      := hades-portal
PORTAL_GROUP     := hades-portal
PORTAL_HOME      := $(PKGLOCALSTATEDIR)/portal
RADIUS_USER      := hades-radius
RADIUS_GROUP     := hades-radius
RADIUS_HOME      := $(PKGLOCALSTATEDIR)/radius
UNAUTH_DNS_USER  := hades-unauth
UNAUTH_DNS_GROUP := hades-unauth
UNAUTH_DNS_HOME  := $(PKGLOCALSTATEDIR)/unauth-dns

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
    PREFIX \
    EXEC_PREFIX \
    BINDIR \
    SBINDIR \
    LIBEXECDIR \
    DATAROOTDIR \
    DATADIR \
    SYSCONFDIR \
    SHAREDSTATEDIR \
    LOCALSTATEDIR \
    RUNSTATEDIR \
    INCLUDEDIR \
    DOCDIR \
    INFODIR \
    HTMLDIR \
    DVIDIR \
    PDFDIR \
    PSDIR \
    LIBDIR \
    LISPDIR \
    LOCALEDIR \
    MANDIR \
    PKGLIBEXECDIR \
    PKGSYSCONFDIR \
    PKGLOCALSTATEDIR \
    PKGRUNSTATEDIR \
    PKGLIBDIR \
    PKGDATADIR \
    ASSETSDIR \
    DBUSCONFDIR \
    SYSTEMDENVDIR \
    SYSTEMDUNITDIR \
    TEMPLATESDIR \
    TMPFILESDDIR \
    VENVDIR \
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
