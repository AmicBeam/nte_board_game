import logging
import os
from logging.handlers import RotatingFileHandler
from functools import wraps
import time

class Logger:
    _logger = logging.getLogger('bot_enjoy')

    def __new__(cls, room_id=None):
        if cls is None or not cls._logger.hasHandlers():
            cls._setup_logger()
        instance = super().__new__(cls)
        instance.room_id = room_id
        return instance

    def __init__(self, room_id=None):
        self.room_id = room_id

    @classmethod
    def _setup_logger(cls):
        """初始化日志配置"""
        if not os.path.exists('logs'):
            os.makedirs('logs')
        cls._logger.setLevel(logging.INFO)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        file_handler = RotatingFileHandler(
            filename=f'logs/bot_{time.strftime("%Y%m%d")}.log',
            maxBytes=10*1024*1024,
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        cls._logger.addHandler(console_handler)
        cls._logger.addHandler(file_handler)

    def info(self, message):
        msg = f"[{self.room_id}] {message}" if self.room_id is not None else message
        Logger._logger.info(msg)

    def error(self, message):
        msg = f"[room_id={self.room_id}] {message}" if self.room_id is not None else message
        Logger._logger.error(msg)

    def warning(self, message):
        msg = f"[room_id={self.room_id}] {message}" if self.room_id is not None else message
        Logger._logger.warning(msg)

    def debug(self, message):
        msg = f"[room_id={self.room_id}] {message}" if self.room_id is not None else message
        Logger._logger.debug(msg)

# 装饰器用于记录函数调用
def log_function_call(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger = Logger()
        try:
            logger.info(f"Calling {func.__name__} with args: {args}, kwargs: {kwargs}")
            result = await func(*args, **kwargs)
            logger.info(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            raise
    return wrapper 