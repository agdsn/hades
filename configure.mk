#!/usr/bin/make -f
# --------- #
# Functions #
# --------- #

# add_substitution(VARIABLE, VALUE)
# ---------------------------------
# Set a variable to a given value and add it to the list of substitution
# variables.
define add_substitution
$(eval
$1 = $2
SUBSTITUTIONS += $1
)
endef

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
# The variable is added to list of substitution variables.
define require_program
$(eval
$1 := $$(call find_program,$2,$3)
ifeq "$$(strip $$($1))" ""
    $$(error Could not find $2)
else
    $$(info Found $2 at $$($1))
endif
SUBSTITUTIONS += $1
)
endef


# -------- #
# Metadata #
# -------- #

$(call add_substitution, PACKAGE_NAME,         hades)
$(call add_substitution, PACKAGE_VERSION,      0.2.0.dev0)
$(call add_substitution, PACKAGE_AUTHOR,       Sebastian Schrader)
$(call add_substitution, PACKAGE_AUTHOR_EMAIL, sebastian.schrader@agdsn.de)
$(call add_substitution, PACKAGE_LICENSE,      MIT)
$(call add_substitution, PACKAGE_URL,          http://github.com/agdsn/hades)

# ----------- #
# Directories #
# ----------- #

# GNU Coding Standards directories
$(call add_substitution, prefix,         /usr/local)
$(call add_substitution, exec_prefix,    $(prefix))
$(call add_substitution, bindir,         $(exec_prefix)/bin)
$(call add_substitution, sbindir,        $(exec_prefix)/sbin)
$(call add_substitution, libexecdir,     $(exec_prefix)/libexec)
$(call add_substitution, datarootdir,    $(prefix)/share)
$(call add_substitution, datadir,        $(datarootdir))
$(call add_substitution, sysconfdir,     $(prefix)/etc)
$(call add_substitution, sharedstatedir, $(prefix)/com)
$(call add_substitution, localstatedir,  $(prefix)/var)
$(call add_substitution, runstatedir,    $(localstatedir)/run)
$(call add_substitution, includedir,     $(prefix)/include)
$(call add_substitution, docdir,         $(datarootdir)/doc/$(PACKAGE_NAME))
$(call add_substitution, infodir,        $(datarootdir)/info)
$(call add_substitution, htmldir,        $(docdir))
$(call add_substitution, dvidir,         $(docdir))
$(call add_substitution, pdfdir,         $(docdir))
$(call add_substitution, psdir,          $(docdir))
$(call add_substitution, libdir,         $(exec_prefix)/lib)
$(call add_substitution, lispdir,        $(datarootdir)/emacs/site-lisp)
$(call add_substitution, localedir,      $(datarootdir)/locale)
$(call add_substitution, mandir,         $(datarootdir)/man)

# Automake-style package directories
$(call add_substitution, pkglibexecdir,    $(libexecdir)/$(PACKAGE_NAME))
$(call add_substitution, pkgsysconfdir,    $(sysconfdir)/$(PACKAGE_NAME))
$(call add_substitution, pkglocalstatedir, $(localstatedir)/$(PACKAGE_NAME))
$(call add_substitution, pkgrunstatedir,   $(runstatedir)/$(PACKAGE_NAME))
$(call add_substitution, pkglibdir,        $(libdir)/$(PACKAGE_NAME))
$(call add_substitution, pkgdatadir,       $(datadir)/$(PACKAGE_NAME))

# Additional directories
$(call add_substitution, assetdir,       $(pkgdatadir)/assests)
$(call add_substitution, dbusconfdir,    $(sysconfdir)/dbus-1/system.d)
$(call add_substitution, systemdenvdir,  /etc/default)
$(call add_substitution, systemdunitdir, /usr/lib/systemd/system)
$(call add_substitution, templatedir,    $(pkgdatadir)/templates)
$(call add_substitution, tmpfilesddir,   $(sysconfdir)/tmpfiles.d)
$(call add_substitution, venvdir,        $(pkglibdir))

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
$(call add_substitution, SYSTEM_GROUP,     hades)
$(call add_substitution, AGENT_USER,       hades-agent)
$(call add_substitution, AGENT_GROUP,      hades-agent)
$(call add_substitution, AGENT_HOME,       $(pkglocalstatedir)/agent)
$(call add_substitution, AUTH_DHCP_USER,   hades-auth-dhcp)
$(call add_substitution, AUTH_DHCP_GROUP,  hades-auth-dhcp)
$(call add_substitution, AUTH_DHCP_HOME,   $(pkglocalstatedir)/auth-dhcp)
$(call add_substitution, AUTH_DNS_USER,    hades-auth-dns)
$(call add_substitution, AUTH_DNS_GROUP,   hades-auth-dns)
$(call add_substitution, AUTH_DNS_HOME,    $(pkglocalstatedir)/auth-dns)
$(call add_substitution, DATABASE_USER,    hades-database)
$(call add_substitution, DATABASE_GROUP,   hades-database)
$(call add_substitution, DATABASE_HOME,    $(pkglocalstatedir)/database)
$(call add_substitution, PORTAL_USER,      hades-portal)
$(call add_substitution, PORTAL_GROUP,     hades-portal)
$(call add_substitution, PORTAL_HOME,      $(pkglocalstatedir)/portal)
$(call add_substitution, RADIUS_USER,      hades-radius)
$(call add_substitution, RADIUS_GROUP,     hades-radius)
$(call add_substitution, RADIUS_HOME,      $(pkglocalstatedir)/radius)
$(call add_substitution, UNAUTH_DNS_USER,  hades-unauth)
$(call add_substitution, UNAUTH_DNS_GROUP, hades-unauth)
$(call add_substitution, UNAUTH_DNS_HOME,  $(pkglocalstatedir)/unauth-dns)

NULL :=

# Disable make's built-in suffix rules
.SUFFIXES:

CONFIGURE_FILES = \
    bower.json \
    conf/hades-agent.service \
    conf/hades-auth-dhcp.service \
    conf/hades-auth-dns.service \
    conf/hades-auth-vrrp.service \
    conf/hades-cleanup.service \
    conf/hades-database.service \
    conf/hades-network.service \
    conf/hades-radius-vrrp.service \
    conf/hades-radius.service \
    conf/hades-refresh.service \
    conf/hades-unauth-dns.service \
    conf/hades-unauth-http.service \
    conf/hades-unauth-portal.service \
    conf/hades-unauth-vrrp.service \
    conf/hades.busconfig \
    conf/hades.tmpfile \
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
