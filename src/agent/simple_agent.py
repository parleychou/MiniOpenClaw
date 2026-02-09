# src/agent/simple_agent.py
"""
简化的 Agent 实现
"""
import time
from typing import Callable, Optional
from terminal.simple_pty import SimplePTY
from agent.simple_filter import SimpleFilter
from utils.logger import Logger


class SimpleAgent:
    """简化的 Agent"""
    
    def __init__(self, config: dict):
        self.config = config
        self.command = config['command']
        self.args = config.get('args', [])
        self.work_dir = config.get('work_dir', '.')
        self.logger = Logger(self.__class__.__name__)
        
        self._pty: Optional[SimplePTY] = None
        self._filter: Optional[SimpleFilter] = None
        self._feishu_callback: Optional[Callable] = None
        self._status = "initialized"
        self._start_time: Optional[float] = None
    
    def set_feishu_callback(self, callback: Callable[[str, str], None]):
        """设置飞书消息回调"""
        self._feishu_callback = callback
        self.logger.info("✅ 飞书回调已设置")
    
    def start(self) -> bool:
        """启动 Agent"""
        self.logger.info("=" * 60)
        self.logger.info("启动 Agent")
        self.logger.info("=" * 60)
        
        # 创建 PTY
        self._pty = SimplePTY(self.command, self.args, self.work_dir)
        
        # 创建过滤器
        self._filter = SimpleFilter(self._on_filtered_output)
        
        # 设置 PTY 输出回调
        self._pty.set_output_callback(self._on_raw_output)
        
        # 启动 PTY
        success = self._pty.start()
        
        if success:
            self._status = "running"
            self._start_time = time.time()
            self.logger.info("✅ Agent 启动成功")
            
            # 等待初始化
            time.sleep(2)
            
            # 自动发送确认（如果是 Claude Code）
            if 'claude' in self.command.lower():
                self.logger.info("[AUTO] 检测到 Claude Code，发送确认...")
                time.sleep(1)
                self._pty.send_input('')  # 发送回车确认
                time.sleep(1)
        else:
            self._status = "failed"
            self.logger.error("❌ Agent 启动失败")
        
        return success
    
    def _on_raw_output(self, line: str):
        """原始输出处理"""
        if self._filter:
            self._filter.process_line(line)
    
    def _on_filtered_output(self, message: str, msg_type: str):
        """过滤后的输出回调"""
        if self._feishu_callback:
            self._feishu_callback(message, msg_type)
        else:
            self.logger.warning("⚠️ 飞书回调未设置")
    
    def send_input(self, text: str):
        """发送输入"""
        if self._pty:
            self._pty.send_input(text)
        else:
            self.logger.error("❌ PTY 未初始化")
    
    def is_running(self) -> bool:
        """检查是否运行中"""
        return self._pty is not None and self._pty.is_running()
    
    def get_status(self) -> dict:
        """获取状态"""
        return {
            "status": self._status if self.is_running() else "stopped",
            "agent_type": self.__class__.__name__,
            "command": self.command,
            "work_dir": self.work_dir,
            "uptime": time.time() - self._start_time if self._start_time else 0,
        }
    
    def get_recent_output(self, lines: int = 30) -> list:
        """获取最近输出"""
        if self._pty:
            return self._pty.get_recent_output(lines)
        return []
    
    def stop(self):
        """停止 Agent"""
        self._status = "stopping"
        if self._pty:
            self._pty.stop()
        self._status = "stopped"
        self.logger.info("Agent 已停止")
