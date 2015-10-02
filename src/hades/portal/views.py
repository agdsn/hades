from flask import request, render_template
from flask.ext.babel import _, lazy_gettext

import arpreq
from hades.portal import app
from hades.common.db import get_groups, get_latest_auth_attempt

messages = {
    'traffic': lazy_gettext("You've exceeded your traffic limit."),
    'violation': lazy_gettext("You violated our Terms of Services. "
                              "Please contact our support."),
    'security': lazy_gettext("We had to block you due to security problems "
                             "with your devices. "
                             "Please contact our support."),
    'default_in_payment': lazy_gettext(
        "You are late with paying your fees. "
        "Please pay the outstanding fees (including late fee). "
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

@app.route("/")
def index():
    try:
        mac = arpreq.arpreq(request.remote_addr)
    except arpreq.ARPError as e:
        content = render_template("error.html",
                                  message=_("Could not determine your MAC "
                                            "address (ARPError)."))
        return content, 500
    if mac is None:
        content = render_template("error.html",
                                  error=_("Could not determine your MAC "
                                          "address (no result)."))
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
