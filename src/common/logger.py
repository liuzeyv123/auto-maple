"""日志系统模块"""

import os
import logging
from datetime import datetime

# 确保logs目录存在
LOGS_DIR = 'logs'
os.makedirs(LOGS_DIR, exist_ok=True)

# 获取当前日期作为日志文件名
today = datetime.now().strftime('%Y-%m-%d')
LOG_FILE = os.path.join(LOGS_DIR, f'{today}.log')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 创建logger实例
logger = logging.getLogger('auto-maple')

# 日志级别常量
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# 便捷函数
def debug(msg, *args, **kwargs):
    """记录调试级别日志"""
    logger.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    """记录信息级别日志"""
    logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    """记录警告级别日志"""
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    """记录错误级别日志"""
    logger.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    """记录严重错误级别日志"""
    logger.critical(msg, *args, **kwargs)