#!/usr/bin/make -Rrf

NULL :=

# ----- #
# Shell #
# ----- #

# Prevent GNU make optimization that tries to detect, if commands may be
# executed directly instead of indirectly via a shell on GNU make earlier than
# 4.2.90 by adding shell construct : &&
# https://github.com/mirror/make/commit/1af314465e5dfe3e8baa839a32a72e83c04f26ef
SHELL := $(shell : && command -v bash)
ifeq ($(strip $(SHELL)),)
$(error Could not find bash)
endif
# Check for .SHELLSTATUS support (GNU make 4.2+)
ifneq ($(.SHELLSTATUS),0)
$(error Your make does not support .SHELLSTATUS)
endif
.SHELLFLAGS := -euo pipefail -c

# --------- #
# Functions #
# --------- #

# add_substitution(VARIABLE, VALUE)
# ---------------------------------
# Set a variable to a given value and add it to the list of substitution
# variables.
define add_substitution
$(eval
$(strip $1) = $(strip $2)
SUBSTITUTIONS += $(strip $1)
)
endef

# xshell(CODE, ERROR)
# -------------------
# Run $(shell CODE) and fail with $(error ERROR) if exit status is non-zero.
define xshell
$(shell $(strip $1))$(if $(filter-out 0,$(.SHELLSTATUS)),$(error Executing $(strip $1) failed with exit status $(.SHELLSTATUS)))
endef

# add_shell_substitution(VARIABLE, CODE)
# --------------------------------------
# Set VARIABLE to the output of executing CODE in a shell and add VARIABLE to
# the list of substitution variables.
define add_shell_substitution
$(if $(findstring undefined,$(origin $(strip $1))),
    $(call add_substitution, $1, $(call xshell,$(strip $2))),
    $(eval SUBSTITUTIONS += $(strip $1))
)
endef

# find_program(NAMES, [PATH])
# ---------------------------
# Find the full path of a program. A specific PATH may be specified optionally.
define find_program
$(firstword $(foreach name,$1,$(wildcard $(addsuffix /$(name),$(subst :, ,$(if $(and $(filter-out undefined,$(origin 2)),$2),$(strip $2),$(PATH)))))))
endef

# require_program(VARIABLE, NAMES, [PATH])
# ----------------------------------------
# Find the full path of program and store the full path in a given variable.
# Abort if the program can not be found. A specific PATH may be specified
# optionally.
# The variable is added to list of substitution variables.
define require_program
$(if
    $(findstring undefined,$(origin $(strip $1))),
    $(call add_substitution,$1,
        $(if $(and $(filter-out undefined,$(origin 3)),$3),
            $(call find_program,$2,$3),
            $(call find_program,$2)
        )
    )
    $(if $($(strip $1)),
        $(info Found $(strip $2) at $($(strip $1))),
        $(error Could not find $(strip $2) in PATH=$(if $(and $(filter-out undefined,$(origin 3)),$3),$(strip $3),$(PATH)))
    ),
    $(info Using user-defined $(strip $2) at $($(strip $1)))
    $(eval SUBSTITUTIONS += $(strip $1))
)
endef

# Don't set variables if clean is the only goal
ifneq ($(MAKECMDGOALS),clean)

# -------- #
# Metadata #
# -------- #

$(call add_substitution, PACKAGE_NAME,         hades)
$(call add_substitution, PACKAGE_VERSION,      0.5.1)
$(call add_substitution, PACKAGE_DESCRIPTION,  Distributed AG DSN RADIUS MAC authentication. Site node agent and captive portal)
$(call add_substitution, PACKAGE_AUTHOR,       Sebastian Schrader)
$(call add_substitution, PACKAGE_AUTHOR_EMAIL, sebastian.schrader@agdsn.de)
$(call add_substitution, PACKAGE_LICENSE,      MIT)
$(call add_substitution, PACKAGE_URL,          https://github.com/agdsn/hades)

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
$(call add_substitution, logdir,         $(localstatedir)/log)

# Automake-style package directories
$(call add_substitution, pkglibexecdir,    $(libexecdir)/$(PACKAGE_NAME))
$(call add_substitution, pkgsysconfdir,    $(sysconfdir)/$(PACKAGE_NAME))
$(call add_substitution, pkglocalstatedir, $(localstatedir)/$(PACKAGE_NAME))
$(call add_substitution, pkgrunstatedir,   $(runstatedir)/$(PACKAGE_NAME))
$(call add_substitution, pkgincludedir,    $(includedir)/$(PACKAGE_NAME))
$(call add_substitution, pkglibdir,        $(libdir)/$(PACKAGE_NAME))
$(call add_substitution, pkgdatadir,       $(datadir)/$(PACKAGE_NAME))
$(call add_substitution, pkglogdir,        $(logdir)/$(PACKAGE_NAME))

# Additional directories
$(call add_shell_substitution, pythonsitedir, python3 -c 'from distutils.sysconfig import get_python_lib; print(get_python_lib())')
$(call add_substitution, assetdir,       $(pythonsitedir)/hades/portal/assets)
$(call add_substitution, systemdenvfile, /etc/default/hades)
$(call add_substitution, templatepath,   $(pkgsysconfdir)/templates:$(pkgdatadir)/templates)
$(call add_substitution, venvdir,        $(NULL))

# Derived paths
$(call add_substitution, AGENT_PID_FILE, $(pkgrunstatedir)/agent/worker.pid)
$(call add_substitution, AUTH_DHCP_HOSTS_FILE, $(pkglocalstatedir)/auth-dhcp/dnsmasq-dhcp.hosts)
$(call add_substitution, AUTH_DHCP_LEASE_FILE, $(pkglocalstatedir)/auth-dhcp/dnsmasq-dhcp.leases)
$(call add_substitution, AUTH_DHCP_PID_FILE, $(pkgrunstatedir)/auth-dhcp/dnsmasq.pid)
$(call add_substitution, AUTH_DHCP_SCRIPT_SOCKET, $(pkgrunstatedir)/auth-dhcp/script.sock)
$(call add_substitution, AUTH_DNS_ALTERNATIVE_PID_FILE, $(pkgrunstatedir)/auth-dns/unbound-alternative.pid)
$(call add_substitution, AUTH_DNS_PRISTINE_PID_FILE, $(pkgrunstatedir)/auth-dns/unbound-pristine.pid)
$(call add_substitution, AUTH_DNS_ROOT_HINTS, /usr/share/dns/root.hints)
$(call add_substitution, AUTH_DNS_TRUST_ANCHOR_FILE, $(pkglocalstatedir)/auth-dns/root.key)
$(call add_substitution, DATABASE_SOCKET_DIRECTORY, $(pkgrunstatedir)/database)
$(call add_substitution, PORTAL_NGINX_PID_FILE, $(pkgrunstatedir)/unauth-http/nginx.pid)
$(call add_substitution, PORTAL_UWSGI_PID_FILE, $(pkgrunstatedir)/unauth-portal/uwsgi.pid)
$(call add_substitution, PORTAL_UWSGI_SOCKET, $(pkgrunstatedir)/unauth-portal/uwsgi.sock)
$(call add_substitution, RADIUS_CLIENTS_FILE, $(pkglocalstatedir)/radius/clients.conf)
$(call add_substitution, RADIUS_PID_FILE, $(pkgrunstatedir)/radius/radiusd.pid)
$(call add_substitution, UNAUTH_DHCP_LEASE_FILE, $(pkgrunstatedir)/unauth-dns/dnsmasq-dhcp.leases)
$(call add_substitution, UNAUTH_DHCP_SCRIPT_SOCKET, $(pkgrunstatedir)/unauth-dhcp/script.sock)
$(call add_substitution, UNAUTH_DNS_PID_FILE, $(pkgrunstatedir)/unauth-dns/dnsmasq.pid)

# ----- #
# Names #
# ----- #

$(call add_substitution, AUTH_DHCP_DBUS_NAME, de.agdsn.hades.auth_dnsmasq)
$(call add_substitution, AUTH_NAMESPACE, auth)
$(call add_substitution, AUTH_VRRP_DBUS_NAME, de.agdsn.hades.auth_vrrp)
$(call add_substitution, DATABASE_NAME, hades)
$(call add_substitution, DEPUTY_DBUS_NAME, de.agdsn.hades.deputy)
$(call add_substitution, LOCAL_MASTER_DATABASE_NAME, foreign)
$(call add_substitution, LOCAL_MASTER_DATABASE_PASSWORD, foreign)
$(call add_substitution, LOCAL_MASTER_DATABASE_USER, foreign)
$(call add_substitution, ROOT_VRRP_DBUS_NAME, de.agdsn.hades.root_vrrp)
$(call add_substitution, UNAUTH_DNS_DBUS_NAME, de.agdsn.hades.unauth_dnsmasq)
$(call add_substitution, UNAUTH_NAMESPACE, unauth)
$(call add_substitution, UNAUTH_VRRP_DBUS_NAME, de.agdsn.hades.unauth_vrrp)

# -------- #
# Programs #
# -------- #

# Runtime programs
$(call require_program,BRIDGE,bridge)
$(call require_program,DBUS_SEND,dbus-send)
$(call require_program,DNSMASQ,dnsmasq)
$(call require_program,IFDOWN,ifdown)
$(call require_program,IFUP,ifup)
$(call require_program,IP,ip)
$(call require_program,IPSET,ipset)
$(call require_program,IPTABLES,iptables)
$(call require_program,IPTABLES_RESTORE,iptables-restore)
$(call require_program,KEEPALIVED,keepalived)
$(call require_program,KILL,kill)
$(call require_program,MOUNT,mount)
$(call require_program,NGINX,nginx)
$(call require_program,PSQL,psql)
$(call require_program,PYTHON3,python3)
$(call require_program,RADIUSD,radiusd freeradius)
$(call require_program,RM,rm)
$(call require_program,SED,sed)
$(call require_program,SYSCTL,sysctl)
$(call require_program,SYSTEMCTL,systemctl)
$(call require_program,TOUCH,touch)
$(call require_program,UMOUNT,umount)
$(call require_program,UNBOUND,unbound)
$(call require_program,UNBOUND_ANCHOR,unbound-anchor)
$(call require_program,UNBOUND_CHECKCONF,unbound-checkconf)
$(call require_program,UNBOUND_CONTROL,unbound-control)
$(call require_program,UWSGI,uwsgi)

ifndef PG_ROOT
PG_VERSION := $(call xshell, command -v perl &>/dev/null && perl -e 'if (my $$version = eval { require PgCommon; PgCommon::get_newest_version(); }) { print $$version; }')
ifneq ($(PG_VERSION),)
get_pg_path := perl -MPgCommon -e 'print get_program_path($$ARGV[0], "$(PG_VERSION)");'
$(call add_shell_substitution, CREATEDB,   $(get_pg_path) createdb)
$(call add_shell_substitution, CREATEUSER, $(get_pg_path) createuser)
$(call add_shell_substitution, PG_CTL,     $(get_pg_path) pg_ctl)
$(call add_shell_substitution, POSTGRES,   $(get_pg_path) postgres)
pg_path = $(NULL)
else # ifneq ($(PG_VERSION),)
pg_path = $(subst :, ,$(PATH))
endif # ifneq ($(PG_VERSION),)
else # ifndef PG_ROOT
pg_path = $(PG_ROOT)/bin
endif # ifndef PG_ROOT

ifneq ($(pg_path),)
$(call require_program, CREATEDB,   createdb,  $(pg_path))
$(call require_program, CREATEUSER, createuser $(pg_path))
$(call require_program, PG_CTL,     pg_ctl,    $(pg_path))
$(call require_program, POSTGRES,   postgres,  $(pg_path))
endif # ifneq ($(pg_path),)

# ----------------- #
# Users and groups  #
# ----------------- #

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

# ---------- #
# Arguments  #
# ---------- #

cli_variables := $(foreach var,$(.VARIABLES),$(if $(findstring command line,$(origin $(var))),$(var)))
$(call add_substitution, CONFIGURE_ARGS, $(foreach var,$(cli_variables),$(var)=$($(var))))

endif # ifneq ($(MAKECMDGOALS),clean)

CONFIGURE_FILES = \
    conf/hades-agent.service \
    conf/hades-auth-alternative-dns.service \
    conf/hades-auth-dhcp.service \
    conf/hades-auth-dhcp-leases.service \
    conf/hades-auth-dhcp-leases.socket \
    conf/hades-auth-netns.service \
    conf/hades-auth-pristine-dns.service \
    conf/hades-auth-vrrp.service \
    conf/hades-cleanup.service \
    conf/hades-database.service \
    conf/hades-deputy.dbus-service \
    conf/hades-deputy.service \
    conf/hades-forced-refresh.service \
    conf/hades-radius.service \
    conf/hades-refresh.service \
    conf/hades-root-vrrp.service \
    conf/hades-root-netns.service \
    conf/hades-unauth-dhcp-leases.service \
    conf/hades-unauth-dhcp-leases.socket \
    conf/hades-unauth-dns.service \
    conf/hades-unauth-http.service \
    conf/hades-unauth-netns.service \
    conf/hades-unauth-portal.service \
    conf/hades-unauth-vrrp.service \
    conf/hades.busconfig \
    conf/hades.tmpfile \
    scripts/check-services.sh \
    scripts/control-database.sh \
    scripts/functions.sh \
    scripts/package-setup.sh \
    scripts/update-trust-anchor.sh \
    setup.py \
    src/hades/bin/config.h \
    src/hades/deputy/interface.xml \
    $(NULL)

# ------- #
# Targets #
# ------- #

all: $(CONFIGURE_FILES) src/hades/constants.py
.PHONY: all

# Disable make's built-in suffix rules
.SUFFIXES:

.FORCE:
.PHONY: .FORCE

$(CONFIGURE_FILES): %: %.in configure.mk .FORCE
	@echo Configuring $@
	@$(SED) $(foreach var,$(SUBSTITUTIONS),-e 's|@$(var)@|$($(var))|g' ) < $< > $@
	@chmod --reference=$< $@
	@if grep --silent -E '@[^@]+@' $@; then \
		echo 'Unsubstituted substitution variables in $@:' >&2; \
		grep --with-filename --line-number -E '@[^@]+@' $@ >&2; \
		exit 1; \
	fi

src/hades/constants.py: configure.mk .FORCE
	@echo Creating $@
	@{ \
		echo '# Generated by configure.mk. Do not modify.'; \
		echo '"""Build-time constants generated by configure.mk"""'; \
		printf '%s = "%s"\n' $(foreach var,$(SUBSTITUTIONS),'$(var)' '$($(var))') | sort -k1; \
	} > $@

clean:
	rm -f $(CONFIGURE_FILES)
	rm -f src/hades/constants.py
.PHONY: clean
