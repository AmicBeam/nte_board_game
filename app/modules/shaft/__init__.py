from flask import Blueprint


blueprint = Blueprint(
    'shaft_module',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static/shaft',
)
