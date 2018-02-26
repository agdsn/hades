#!/usr/bin/make -Rrf
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
$(call add_substitution, PACKAGE_VERSION,      0.4.0)
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
$(call add_substitution, pythonsitedir,  $(shell python3 -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())"))
$(call add_substitution, assetdir,       $(pythonsitedir)/hades/portal/assets)
$(call add_substitution, systemdenvfile, /etc/default/hades)
$(call add_substitution, templatedir,    $(pkgdatadir)/templates)
$(call add_substitution, venvdir,        $(NULL))

# Derived paths
$(call add_substitution, AGENT_PID_FILE, $(pkgrunstatedir)/agent/worker.pid)
$(call add_substitution, AUTH_DHCP_DBUS_NAME, de.agdsn.hades.auth_dnsmasq)
$(call add_substitution, AUTH_DHCP_PID_FILE, $(pkgrunstatedir)/auth-dhcp/dnsmasq.pid)
$(call add_substitution, AUTH_DHCP_LEASE_FILE, $(pkglocalstatedir)/auth-dhcp/dnsmasq-dhcp.leases)
$(call add_substitution, AUTH_DHCP_HOSTS_FILE, $(pkglocalstatedir)/auth-dhcp/dnsmasq-dhcp.hosts)
$(call add_substitution, AUTH_DNS_PRISTINE_PID_FILE, $(pkgrunstatedir)/auth-dns/unbound-pristine.pid)
$(call add_substitution, AUTH_DNS_ALTERNATIVE_PID_FILE, $(pkgrunstatedir)/auth-dns/unbound-alternative.pid)
$(call add_substitution, AUTH_DNS_ROOT_HINTS, /usr/share/dns/root.hints)
$(call add_substitution, AUTH_DNS_TRUST_ANCHOR_FILE, $(pkglocalstatedir)/auth-dns/root.key)
$(call add_substitution, AUTH_NAMESPACE, auth)
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
$(call add_substitution, UNAUTH_DHCP_LEASE_FILE, $(pkgrunstatedir)/unauth-dns/dnsmasq-dhcp.leases)
$(call add_substitution, UNAUTH_DNS_DBUS_NAME, de.agdsn.hades.unauth_dnsmasq)
$(call add_substitution, UNAUTH_DNS_PID_FILE, $(pkgrunstatedir)/unauth-dns/dnsmasq.pid)
$(call add_substitution, UNAUTH_NAMESPACE, unauth)

# -------- #
# Programs #
# -------- #

$(call require_program,SHELL,bash)

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
$(call require_program,PG_CONFIG,pg_config)
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
    conf/hades-agent.service \
    conf/hades-auth-alternative-dns.service \
    conf/hades-auth-dhcp.service \
    conf/hades-auth-netns.service \
    conf/hades-auth-netns-cleanup.service \
    conf/hades-auth-pristine-dns.service \
    conf/hades-auth-vrrp.service \
    conf/hades-cleanup.service \
    conf/hades-database.service \
    conf/hades-deputy.service \
    conf/hades-deputy.dbus-service \
    conf/hades-radius-vrrp.service \
    conf/hades-radius.service \
    conf/hades-refresh.service \
    conf/hades-root-netns.service \
    conf/hades-root-netns-cleanup.service \
    conf/hades-forced-refresh.service \
    conf/hades-unauth-dns.service \
    conf/hades-unauth-http.service \
    conf/hades-unauth-netns.service \
    conf/hades-unauth-netns-cleanup.service \
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

all: $(CONFIGURE_FILES) src/hades/constants.py

$(CONFIGURE_FILES): %: %.in configure.mk .FORCE
	@echo Configuring $@
	@$(SED) $(foreach var,$(SUBSTITUTIONS),-e 's|@$(var)@|$($(var))|g' ) < $< > $@
	@chmod --reference=$< $@

src/hades/constants.py: configure.mk .FORCE
	@echo Creating $@
	@echo '# Generated by configure.mk. Do not modify.' > $@
	@printf '%s = "%s"\n' $(foreach var,$(SUBSTITUTIONS),'$(var)' '$($(var))') > $@

clean:
	$(RM) -f $(CONFIGURE_FILES)
	$(RM) -f src/hades/constants.py

.FORCE:

.PHONY: all clean .FORCE
