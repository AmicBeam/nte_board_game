import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('NTE_SECRET_KEY', 'nte-board-game-dev-secret')
DATABASE_PATH = os.getenv('NTE_DATABASE_PATH', str(BASE_DIR / 'nte_board_game.db'))
TOKEN_TTL_HOURS = int(os.getenv('NTE_TOKEN_TTL_HOURS', '72'))
DEFAULT_MAP_ID = os.getenv('NTE_DEFAULT_MAP_ID', 'lower_relay_district')
LOG_DIR = Path(os.getenv('NTE_LOG_DIR', str(BASE_DIR / 'logs')))
MOVE_STEP_LIMIT = int(os.getenv('NTE_MOVE_STEP_LIMIT', '64'))
DRAW_LOOP_LIMIT = int(os.getenv('NTE_DRAW_LOOP_LIMIT', '64'))
