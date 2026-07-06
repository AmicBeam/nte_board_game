from flask import Flask, g, request

from app.config import IS_DEV_ENV, SECRET_KEY
from app.db import init_db
from app.models import (
    AccessToken,
    DeckBuild,
    GameRun,
    LoginCode,
    Player,
    PlayerTutorial,
    Room,
    RoomMember,
    ShaftAxis,
    ShaftAxisCharacter,
    ShaftAxisFavorite,
    ShaftAxisLike,
)
from app.utils.logger import get_logger, setup_logging


def create_app() -> Flask:
    setup_logging()
    logger = get_logger('nte.app')
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['IS_DEV_ENV'] = IS_DEV_ENV
    init_db([
        Player,
        PlayerTutorial,
        LoginCode,
        AccessToken,
        DeckBuild,
        Room,
        RoomMember,
        GameRun,
        ShaftAxis,
        ShaftAxisCharacter,
        ShaftAxisLike,
        ShaftAxisFavorite,
    ])

    @app.before_request
    def attach_log_id():
        g.log_id = request.headers.get('X-Log-Id') or 'log-unknown'
        if request.path.startswith('/api/'):
            logger.info('api request log_id=%s method=%s path=%s', g.log_id, request.method, request.path)

    @app.after_request
    def add_static_cache_headers(response):
        if request.path.startswith('/static/images/characters/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        if request.path.startswith('/api/'):
            response.headers['X-Log-Id'] = getattr(g, 'log_id', 'log-unknown')
            logger.info(
                'api response log_id=%s method=%s path=%s status=%s',
                getattr(g, 'log_id', 'log-unknown'),
                request.method,
                request.path,
                response.status_code,
            )
        return response

    from .routes import main_bp

    app.register_blueprint(main_bp)
    logger.info('Flask app initialized successfully.')
    return app
