from flask import Blueprint


blueprint = Blueprint(
    'preteam_module',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static/preteam',
)
