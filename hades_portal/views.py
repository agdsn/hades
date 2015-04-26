from flask import request, render_template
import arpreq
from hades_portal import app
from hades_portal.db import get_groups, get_latest_auth_attempt

@app.route("/")
def index():
    try:
        mac = arpreq.arpreq(request.remote_addr)
    except arpreq.ARPError as e:
        return render_template("base.html", error=True)
    if mac is None:
        return render_template("base.html", error=True)
    mac_groups = get_groups(mac)
    last_auth_groups, last_auth_date = get_latest_auth_attempt(mac)
    return render_template(
        "base.html",
        violation='violation' in mac_groups,
        security='security' in mac_groups,
        default_in_payment='default_in_payment' in mac_groups,
        traffic='traffic' in mac_groups,
        unknown=not mac_groups,
        wrong_port='unknown' in last_auth_groups,
        membership_ended='membership_ended' in mac_groups,
        last_auth_groups=last_auth_groups,
        last_auth_date=last_auth_date,
        mac=mac,
    )


@app.route("/status")
def status():
    pass
