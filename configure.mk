#!/usr/bin/make -Rrf

NULL :=

# ----- #
# Shell #
# ----- #

SHELL := $(shell if output="$$(command -v bash)"; then echo "$${output}"; fi)
ifeq ($(strip $(SHELL)),)
$(error Could not find bash)
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

# add_shell_substitution(VARIABLE, CODE)
# --------------------------------------
# Set VARIABLE to the output of executing CODE in a shell and add VARIABLE to
# the list of substitution variables.
define add_shell_substitution
$(call add_substitution,$1,$(shell if output="$$($(strip $2))"; then echo "$$output"; fi))
$(if $($(strip $1)),,
	$(error Failed to execute $(strip $2) (No output or non-zero exit status))
)
endef

# find_program(NAMES, [PATH])
# ---------------------------
# Find the full path of a program. A specific PATH may be specified optionally.
define find_program
$(shell
    $(if $(strip $2),PATH="$(strip $2)";,)
    IFS=':';
    for path in $$PATH; do
        IFS=;
        for exec in $(strip $1); do
            if [[ -x "$${path}/$${exec}" ]]; then
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
$(call add_substitution,$1,$(call find_program,$2,$3))
$(if $($(strip $1)),
    $(info Found $(strip $2) at $($(strip $1))),
    $(error Could not find $(strip $2) in PATH=$(if $(strip $3)),$(PATH),$(strip $3))
)
endef

# Don't set variables if clean is the only goal
ifneq ($(MAKECMDGOALS),clean)

# -------- #
# Metadata #
# -------- #

$(call add_substitution, PACKAGE_NAME,         hades)
$(call add_substitution, PACKAGE_VERSION,      0.4.0)
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
$(call add_substitution, AUTH_DHCP_DBUS_NAME, de.agdsn.hades.auth_dnsmasq)
$(call add_substitution, AUTH_DHCP_HOSTS_FILE, $(pkglocalstatedir)/auth-dhcp/dnsmasq-dhcp.hosts)
$(call add_substitution, AUTH_DHCP_LEASE_FILE, $(pkglocalstatedir)/auth-dhcp/dnsmasq-dhcp.leases)
$(call add_substitution, AUTH_DHCP_PID_FILE, $(pkgrunstatedir)/auth-dhcp/dnsmasq.pid)
$(call add_substitution, AUTH_DNS_ALTERNATIVE_PID_FILE, $(pkgrunstatedir)/auth-dns/unbound-alternative.pid)
$(call add_substitution, AUTH_DNS_PRISTINE_PID_FILE, $(pkgrunstatedir)/auth-dns/unbound-pristine.pid)
$(call add_substitution, AUTH_DNS_ROOT_HINTS, /usr/share/dns/root.hints)
$(call add_substitution, AUTH_DNS_TRUST_ANCHOR_FILE, $(pkglocalstatedir)/auth-dns/root.key)
$(call add_substitution, AUTH_NAMESPACE, auth)
$(call add_substitution, AUTH_VRRP_DBUS_NAME, de.agdsn.hades.auth_vrrp)
$(call add_substitution, DATABASE_NAME, hades)
$(call add_substitution, DATABASE_SOCKET_DIRECTORY, $(pkgrunstatedir)/database)
$(call add_substitution, DEPUTY_DBUS_NAME, de.agdsn.hades.deputy)
$(call add_substitution, LOCAL_MASTER_DATABASE_NAME, foreign)
$(call add_substitution, LOCAL_MASTER_DATABASE_PASSWORD, foreign)
$(call add_substitution, LOCAL_MASTER_DATABASE_USER, foreign)
$(call add_substitution, PORTAL_NGINX_PID_FILE, $(pkgrunstatedir)/unauth-http/nginx.pid)
$(call add_substitution, PORTAL_UWSGI_PID_FILE, $(pkgrunstatedir)/unauth-portal/uwsgi.pid)
$(call add_substitution, PORTAL_UWSGI_SOCKET, $(pkgrunstatedir)/unauth-portal/uwsgi.sock)
$(call add_substitution, RADIUS_CLIENTS_FILE, $(pkglocalstatedir)/radius/clients.conf)
$(call add_substitution, RADIUS_PID_FILE, $(pkgrunstatedir)/radius/radiusd.pid)
$(call add_substitution, RADIUS_VRRP_DBUS_NAME, de.agdsn.hades.radius_vrrp)
$(call add_substitution, UNAUTH_DHCP_LEASE_FILE, $(pkgrunstatedir)/unauth-dns/dnsmasq-dhcp.leases)
$(call add_substitution, UNAUTH_DNS_DBUS_NAME, de.agdsn.hades.unauth_dnsmasq)
$(call add_substitution, UNAUTH_DNS_PID_FILE, $(pkgrunstatedir)/unauth-dns/dnsmasq.pid)
$(call add_substitution, UNAUTH_NAMESPACE, unauth)
$(call add_substitution, UNAUTH_VRRP_DBUS_NAME, de.agdsn.hades.unauth_vrrp)

# -------- #
# Programs #
# -------- #

# Runtime programs
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

get_pg_version := perl -MPgCommon -e 'print get_newest_version();'

$(call add_shell_substitution, PG_VERSION, $(get_pg_version))

get_pg_path := perl -MPgCommon -e 'print get_program_path($$ARGV[0], "$(PG_VERSION)");'

$(call add_shell_substitution, CREATEDB,   $(get_pg_path) createdb)
$(call add_shell_substitution, CREATEUSER, $(get_pg_path) createuser)
$(call add_shell_substitution, PG_CTL,     $(get_pg_path) pg_ctl)
$(call add_shell_substitution, POSTGRES,   $(get_pg_path) postgres)

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
    conf/hades-auth-netns-cleanup.service \
    conf/hades-auth-netns.service \
    conf/hades-auth-pristine-dns.service \
    conf/hades-auth-vrrp.service \
    conf/hades-cleanup.service \
    conf/hades-database.service \
    conf/hades-deputy.dbus-service \
    conf/hades-deputy.service \
    conf/hades-forced-refresh.service \
    conf/hades-radius-vrrp.service \
    conf/hades-radius.service \
    conf/hades-refresh.service \
    conf/hades-root-netns-cleanup.service \
    conf/hades-root-netns.service \
    conf/hades-unauth-dns.service \
    conf/hades-unauth-http.service \
    conf/hades-unauth-netns-cleanup.service \
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
		printf '%s = "%s"\n' $(foreach var,$(SUBSTITUTIONS),'$(var)' '$($(var))') | sort -k1; \
	} > $@

clean:
	rm -f $(CONFIGURE_FILES)
	rm -f src/hades/constants.py
.PHONY: clean
