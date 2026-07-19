import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.dao import issue_mock_login
from app.db import init_db
from app.models import AccessToken, DeckBuild, GameRun, LoginCode, Player
from app.utils.logger import get_logger, setup_logging


def main():
    setup_logging()
    logger = get_logger('nte.seed_mock_account')
    init_db([Player, LoginCode, AccessToken, DeckBuild, GameRun])
    player = issue_mock_login('10001', 'Mock Runner', '654321')
    player.shaft_test_whitelisted = True
    player.save(only=[Player.shaft_test_whitelisted])
    logger.info('Mock account seeded into shared database.')
    print('mock-account-seeded 10001 654321')


if __name__ == '__main__':
    main()
