import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

NTE_ENV = os.getenv('NTE_ENV', 'production').strip().lower()
IS_DEV_ENV = NTE_ENV == 'development'
SECRET_KEY = os.getenv('NTE_SECRET_KEY', 'nte-board-game-dev-secret')
DATABASE_PATH = os.getenv('NTE_DATABASE_PATH', str(BASE_DIR / 'nte_board_game.db'))
TOKEN_TTL_HOURS = int(os.getenv('NTE_TOKEN_TTL_HOURS', '72'))
DEFAULT_MAP_ID = os.getenv('NTE_DEFAULT_MAP_ID', 'rob_bank')
LOG_DIR = Path(os.getenv('NTE_LOG_DIR', str(BASE_DIR / 'logs')))
MOVE_STEP_LIMIT = int(os.getenv('NTE_MOVE_STEP_LIMIT', '64'))
DRAW_LOOP_LIMIT = int(os.getenv('NTE_DRAW_LOOP_LIMIT', '64'))

IDENTIFICATION_EXP_SCALE = 100
IDENTIFICATION_RARITY_EXP = {
    'n': 1,
    'r': 3,
    'sr': 5,
    'ur': 10,
}
IDENTIFICATION_LEVEL_EXP_REQUIREMENTS = {
    1: 3,
    2: 5,
    3: 8,
}
IDENTIFICATION_POST_MAX_BUFF_EXP = 13
IDENTIFICATION_COMBO_BONUS_PERCENT_PER_STACK = 10
IDENTIFICATION_COMBO_MAX_BONUS_PERCENT = 100
