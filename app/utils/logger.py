import logging
from datetime import datetime
from pathlib import Path
from typing import TextIO

from app.config import LOG_DIR


class DailyFileHandler(logging.Handler):
    def __init__(self, log_dir: Path):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_date: str | None = None
        self.stream: TextIO | None = None

    def _open_for_today(self) -> None:
        today = datetime.now().strftime('%Y-%m-%d')
        if self.current_date == today and self.stream is not None:
            return
        if self.stream is not None:
            self.stream.close()
        file_path = self.log_dir / f'{today}.log'
        self.stream = file_path.open('a', encoding='utf-8')
        self.current_date = today

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._open_for_today()
            message = self.format(record)
            self.stream.write(message + '\n')
            self.stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None
        super().close()


def setup_logging() -> None:
    root_logger = logging.getLogger()
    if getattr(root_logger, '_nte_logging_ready', False):
        return
    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = DailyFileHandler(LOG_DIR)
    file_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger._nte_logging_ready = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
