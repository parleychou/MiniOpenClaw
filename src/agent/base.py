import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional
from terminal.pty_manager import PTYManager, WinPTYManager
from agent.output_filter import OutputFilter
from utils.logger import Logger


class BaseAgent(ABC):
    """Agent基类"""

    def __init__(self, config: dict, filter_config: dict):
        self.config = config
        self.command = config['command']
        self.args = config.get('args', [])
        self.work_dir = config.get('work_dir', '.')
        self.logger = Logger(self.__class__.__name__)
        
        self._pty: Optional[PTYManager] = None
        self._output_filter: Optional[OutputFilter] = None
        self._feishu_callback: Optional[Callable] = None
        self._status = "initialized"
        self._start_time: Optional[float] = None
        self._command_count = 0

    def set_feishu_callback(self, callback: Callable[[str, str], None]):
        """设置飞书消息回调"""
        self._feishu_callback = callback

    def init_filter(self, filter_config: dict):
        """初始化输出过滤器"""
        self._output_filter = OutputFilter(filter_config, self._on_filtered_output)

    def _on_filtered_output(self, message: str, msg_type: str):
        """过滤后的输出回调"""
        self.logger.debug(f"[CALLBACK] _feishu_callback 是否设置: {self._feishu_callback is not None}")
        if self._feishu_callback:
            self.logger.debug(f"[CALLBACK] 调用 _feishu_callback")
            self._feishu_callback(message, msg_type)
        else:
            self.logger.warning(f"[CALLBACK] _feishu_callback 未设置，无法发送消息")
        # 同时在控制台显示
        self.logger.info(f"[→飞书][{msg_type}] {message[:100]}...")

    def start(self) -> bool:
        """启动Agent"""
        # 获取额外环境变量（子类可覆盖）
        extra_env = getattr(self, 'extra_env', {})

        # 在 Windows 上优先使用 WinPTYManager（提供真实的 PTY）
        import sys
        if sys.platform == 'win32':
            pty_manager = WinPTYManager(self.command, self.args, self.work_dir, extra_env)
        else:
            pty_manager = PTYManager(self.command, self.args, self.work_dir, extra_env)
        
        pty_manager.set_output_callback(self._on_raw_output)

        success = pty_manager.start()

        self._pty = pty_manager

        if success:
            self._status = "running"
            self._start_time = time.time()
            
            # 等待初始化完成
            time.sleep(2)
            
            # 自动处理 Claude Code 的确认提示
            if 'claude' in self.command.lower():
                self.logger.info("[AUTO] 检测到 Claude Code，自动发送确认...")
                # 发送 Down 箭头键选择 "Yes, I accept"
                if hasattr(self._pty, '_pty') and self._pty._pty:
                    self._pty._pty.write('\x1b[B')  # Down arrow
                    time.sleep(0.5)
                    self._pty._pty.write('\r')  # Enter
                    self.logger.info("[AUTO] 已发送确认，等待 Claude Code 启动...")
                    time.sleep(3)
        else:
            self._status = "failed"

        return success

    def _on_raw_output(self, line: str):
        """原始输出处理"""
        if self._output_filter:
            self._output_filter.process_line(line)
        else:
            # 如果没有过滤器，直接调用回调并打印到控制台
            self._on_filtered_output(line, "text")
        # 控制台也显示
        print(f"  {line}")

    def send_input(self, text: str):
        """发送输入"""
        if self._pty:
            self._command_count += 1
            self._pty.send_input(text)
            if self._output_filter:
                self._output_filter.reset_state("processing")

    def is_running(self) -> bool:
        """检查是否运行中"""
        return self._pty is not None and self._pty.is_running()

    def get_status(self) -> dict:
        """获取状态信息"""
        return {
            "status": self._status if self.is_running() else "stopped",
            "agent_type": self.__class__.__name__,
            "command": self.command,
            "work_dir": self.work_dir,
            "uptime": time.time() - self._start_time if self._start_time else 0,
            "command_count": self._command_count,
            "filter_state": self._output_filter.get_state() if self._output_filter else "N/A",
            "idle_time": self._output_filter.get_idle_time() if self._output_filter else 0,
        }

    def get_recent_output(self, lines: int = 30) -> list:
        """获取最近输出"""
        if self._output_filter:
            return self._output_filter.get_accumulated_output(lines)
        elif self._pty:
            return self._pty.get_recent_output(lines)
        return []

    def stop(self):
        """停止Agent"""
        self._status = "stopping"
        if self._pty:
            self._pty.stop()
        self._status = "stopped"