from flask import Blueprint
from flask.templating import render_template

blueprint = Blueprint('views', __name__, static_folder="../static")


@blueprint.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@blueprint.route("/switches/", methods=["GET"])
def switches():
    return render_template("switches.html")


@blueprint.route("/switch/<device_id>/config/")
def switch_config(device_id):
    '''
    opens page for configuring only one device
    '''
    return ('', 200)


@blueprint.route("/view/<view_id>", methods=["GET"])
def view(view_id):
    return (500, 'Nothing')
