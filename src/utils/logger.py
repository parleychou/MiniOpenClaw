import os
import sys
import time
import logging
from datetime import datetime
from colorama import Fore, Style


class ColoredFormatter(logging.Formatter):
    """彩色日志格式"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
        record.name = f"{Fore.BLUE}{record.name}{Style.RESET_ALL}"
        return super().format(record)


class Logger:
    """统一日志管理"""
    
    _initialized = False
    _log_dir = None

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
        if not Logger._initialized:
            Logger._initialize()

    @classmethod
    def _initialize(cls):
        """初始化日志系统"""
        cls._initialized = True
        cls._log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'logs'
        )
        os.makedirs(cls._log_dir, exist_ok=True)

        root = logging.getLogger()
        root.setLevel(logging.DEBUG)

        # 控制台处理器 - 使用 UTF-8 编码
        # 在 Windows 上，强制使用 UTF-8 编码输出
        if sys.platform == 'win32':
            # 尝试设置控制台为 UTF-8 模式
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleOutputCP(65001)  # UTF-8
            except:
                pass
        
        # 使用支持 UTF-8 的 StreamHandler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(ColoredFormatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        ))
        root.addHandler(console)

        # 文件处理器
        log_file = os.path.join(cls._log_dir, f"agent_bridge_{datetime.now():%Y%m%d}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        ))
        root.addHandler(file_handler)

        # 降低第三方库日志级别
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)

    def debug(self, msg): 
        try:
            self.logger.debug(msg)
        except UnicodeEncodeError:
            # 如果遇到编码错误，移除 emoji 后重试
            safe_msg = msg.encode('ascii', 'ignore').decode('ascii')
            self.logger.debug(safe_msg)
    
    def info(self, msg): 
        try:
            self.logger.info(msg)
        except UnicodeEncodeError:
            safe_msg = msg.encode('ascii', 'ignore').decode('ascii')
            self.logger.info(safe_msg)
    
    def warning(self, msg): 
        try:
            self.logger.warning(msg)
        except UnicodeEncodeError:
            safe_msg = msg.encode('ascii', 'ignore').decode('ascii')
            self.logger.warning(safe_msg)
    
    def error(self, msg): 
        try:
            self.logger.error(msg)
        except UnicodeEncodeError:
            safe_msg = msg.encode('ascii', 'ignore').decode('ascii')
            self.logger.error(safe_msg)
    
    def critical(self, msg): 
        try:
            self.logger.critical(msg)
        except UnicodeEncodeError:
            safe_msg = msg.encode('ascii', 'ignore').decode('ascii')
            self.logger.critical(safe_msg)