from flask import Flask

from app.config import SECRET_KEY
from app.db import init_db
from app.models import AccessToken, DeckBuild, GameRun, LoginCode, Player, Room, RoomMember
from app.utils.logger import get_logger, setup_logging


def create_app() -> Flask:
    setup_logging()
    logger = get_logger('nte.app')
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    init_db([Player, LoginCode, AccessToken, DeckBuild, Room, RoomMember, GameRun])

    from .routes import main_bp

    app.register_blueprint(main_bp)
    logger.info('Flask app initialized successfully.')
    return app
