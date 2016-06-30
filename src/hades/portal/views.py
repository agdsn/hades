import logging

import arpreq
from flask import request, render_template
from flask.ext.babel import _, lazy_gettext

from hades.common.db import get_groups, get_latest_auth_attempt
from hades.portal import app, babel

logger = logging.getLogger(__name__)


messages = {
    'traffic': lazy_gettext("You've exceeded your traffic limit."),
    'violation': lazy_gettext("You violated our Terms of Services. "
                              "Please contact our support."),
    'security': lazy_gettext("We had to block you due to security problems "
                             "with your devices. "
                             "Please contact our support."),
    'default_in_payment': lazy_gettext(
        "You are late with paying your fees. "
        "Please pay the outstanding fees. "
        "To regain network connectivity immediately, inform our support. "
        "Otherwise your account will be re-enabled as soon as your money "
        "arrived on our bank account."),
    'wrong_port': lazy_gettext("According to our records you live in a "
                               "different room. "
                               "Please inform us of your relocation."),
    'unknown': lazy_gettext("We don't recognize your MAC address. "
                            "If you are already a AG DSN member, you are "
                            "probably using a different device, please tell us "
                            "its MAC address. "
                            "If you are not a member, please apply."),
    'membership_ended': lazy_gettext("Your current membership status does not "
                                     "allow network access. "
                                     "Please contact our support.")
}


@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(['de', 'en'])


@app.route("/")
def index():
    ip = request.remote_addr
    try:
        mac = arpreq.arpreq(ip)
    except OSError as e:
        logger.execption("Could not resolve IP {} into MAC: {}".format(ip, e))
        content = render_template("error.html",
                                  message=_("An error occurred while resolving "
                                            "IP address into a MAC address."))
        return content, 500
    if mac is None:
        content = render_template("error.html",
                                  error=_("No MAC address could be found for "
                                          "your IP address {}".format(ip)))
        return content, 500
    mac_groups = get_groups(mac)
    latest_auth_attempt = get_latest_auth_attempt(mac)
    if latest_auth_attempt:
        last_auth_groups, last_auth_date = latest_auth_attempt
    else:
        last_auth_groups, last_auth_date = [], None
    reasons = [messages[group] for group in mac_groups if group in messages]
    show_mac = False
    if not mac_groups:
        reasons.append(messages['unknown'])
        show_mac = True
    if 'unknown' in last_auth_groups and mac_groups:
        reasons.append(messages['wrong_port'])
    return render_template(
        "status.html", reasons=reasons,
        mac=mac,
        show_mac=show_mac,
    )
