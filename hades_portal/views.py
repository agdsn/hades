from flask import request, render_template
from flask_babel import _
import arpreq
from hades_portal import app
from hades_portal.db import get_groups, get_latest_auth_attempt

@app.route("/")
def index():
    try:
        mac = arpreq.arpreq(request.remote_addr)
    except arpreq.ARPError as e:
        content = render_template("error.html",
                                  message=_("Could not determine your MAC "
                                            "address"))
        return content, 500
    if mac is None:
        content = render_template("error.html",
                                  error=_("Could not determine your MAC "
                                          "address."))
        return content, 500
    mac_groups = get_groups(mac)
    latest_auth_attempt = get_latest_auth_attempt(mac)
    if latest_auth_attempt:
        last_auth_groups, last_auth_date = latest_auth_attempt
    else:
        last_auth_groups, last_auth_date = [], None
    return render_template(
        "status.html",
        violation='violation' in mac_groups,
        security='security' in mac_groups,
        default_in_payment='default_in_payment' in mac_groups,
        traffic='traffic' in mac_groups,
        unknown=not mac_groups,
        wrong_port='unknown' in last_auth_groups,
        membership_ended='membership_ended' in mac_groups,
        mac=mac,
    )


@app.route("/status")
def status():
    pass
