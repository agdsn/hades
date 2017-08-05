import arpreq
import contextlib

import sqlalchemy.exc
from flask import render_template, request
from flask_babel import _, lazy_gettext

from hades.common.db import create_engine, get_groups, get_latest_auth_attempt
from hades.config.loader import get_config
from hades.portal import app, babel

logger = app.logger


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
engine = None


@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(['de', 'en'])


# noinspection PyUnusedLocal
@app.errorhandler(sqlalchemy.exc.OperationalError)
def handle_database_error(error):
    content = render_template("error.html",
                              message=_("The database is unavailable"))
    return content, 500


@app.before_first_request
def init_engine():
    global engine
    config = get_config(runtime_checks=True)
    engine = create_engine(config)


@app.route("/")
def index():
    ip = request.remote_addr
    try:
        mac = arpreq.arpreq(ip)
    except OSError as e:
        logger.exception("Could not resolve IP {} into MAC: {}".format(ip, e))
        content = render_template("error.html",
                                  message=_("An unexpected error occurred "
                                            "while resolving your IP address "
                                            "into a MAC address."))
        return content, 500
    if mac is None:
        content = render_template("error.html",
                                  error=_("No MAC address could be found for "
                                          "your IP address {}".format(ip)))
        return content, 500

    with contextlib.closing(engine.connect()) as connection, connection.begin():
        mac_groups = list(get_groups(connection, mac))

        if not mac_groups:
            return render_template("status.html", reasons=[messages['unknown']],
                                   mac=mac, show_mac=True)

        latest_auth_attempt = get_latest_auth_attempt(connection, mac)
        if not latest_auth_attempt:
            content = render_template("error.html",
                                      error=_("No authentication attempt found "
                                              "for your MAC address."))
            return content, 500

        nas_ip_address, nas_port_id, *ignore = latest_auth_attempt

        port_groups = [group for nai, npi, group in mac_groups
                       if nas_ip_address == nai and nas_port_id == npi]

        if not port_groups:
            return render_template("status.html", mac=mac, show_mac=False,
                                   reasons=[messages['wrong_port']])

        reasons = [messages[group] for group in port_groups
                   if group in messages]

        return render_template("status.html", reasons=reasons,
                               mac=mac, show_mac=False)
