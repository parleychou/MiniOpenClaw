import time
import threading
from typing import Optional
from utils.logger import Logger

logger = Logger("monitor")


class StatusMonitor:
    """Agent 执行状态监控"""

    def __init__(self, config: dict, agent):
        self.config = config
        self.agent = agent
        self.check_interval = config.get('check_interval', 5)
        self.timeout_threshold = config.get('timeout_threshold', 300)
        self.heartbeat_interval = config.get('heartbeat_interval', 60)
        
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._last_command_time: Optional[float] = None
        self._current_command: Optional[str] = None
        self._command_history = []
        self._alerts = []
        self._feishu_alert_callback = None

    def set_alert_callback(self, callback):
        """设置告警回调"""
        self._feishu_alert_callback = callback

    def start(self):
        """启动监控"""
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("状态监控已启动")

    def stop(self):
        """停止监控"""
        self._running = False

    def record_command(self, command: str):
        """记录命令执行"""
        self._current_command = command
        self._last_command_time = time.time()
        self._command_history.append({
            "command": command[:200],
            "time": time.time(),
            "status": "executing"
        })
        # 只保留最近100条
        if len(self._command_history) > 100:
            self._command_history = self._command_history[-100:]

    def _monitor_loop(self):
        """监控主循环"""
        last_heartbeat = time.time()
        
        while self._running:
            try:
                # 检查Agent状态
                if self.agent and not self.agent.is_running():
                    self._alert("⚠️ Agent 进程已退出，可能需要重启")
                
                # 检查执行超时
                if (self._last_command_time and 
                    time.time() - self._last_command_time > self.timeout_threshold):
                    elapsed = int(time.time() - self._last_command_time)
                    self._alert(
                        f"⏰ 命令执行超时 ({elapsed}s)\n"
                        f"当前命令: {self._current_command[:100] if self._current_command else 'N/A'}"
                    )
                    # 重置避免重复告警
                    self._last_command_time = None
                
                # 心跳
                if time.time() - last_heartbeat > self.heartbeat_interval:
                    last_heartbeat = time.time()
                    logger.debug("心跳正常")
                
            except Exception as e:
                logger.error(f"监控异常: {e}")
            
            time.sleep(self.check_interval)

    def _alert(self, message: str):
        """发送告警"""
        logger.warning(f"告警: {message}")
        self._alerts.append({
            "message": message,
            "time": time.time()
        })
        if self._feishu_alert_callback:
            self._feishu_alert_callback(message)

    def get_status_report(self) -> str:
        """获取状态报告"""
        if not self.agent:
            return "❌ Agent 未初始化"
        
        status = self.agent.get_status()
        
        # 格式化
        uptime = int(status.get('uptime', 0))
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        report = (
            f"📊 系统状态报告\n"
            f"{'━' * 35}\n"
            f"🤖 Agent: {status.get('agent_type', 'N/A')}\n"
            f"📌 状态: {status.get('status', 'unknown')}\n"
            f"📂 目录: {status.get('work_dir', 'N/A')}\n"
            f"⏱️ 运行: {hours}h {minutes}m {seconds}s\n"
            f"📝 命令: {status.get('command_count', 0)} 次\n"
            f"🔄 阶段: {status.get('filter_state', 'N/A')}\n"
            f"💤 空闲: {int(status.get('idle_time', 0))}s\n"
        )
        
        # 最近命令
        if self._command_history:
            report += f"\n📋 最近命令:\n"
            for cmd in self._command_history[-5:]:
                report += f"  • {cmd['command'][:50]}\n"
        
        # 最近告警
        recent_alerts = [a for a in self._alerts if time.time() - a['time'] < 300]
        if recent_alerts:
            report += f"\n⚠️ 最近告警:\n"
            for alert in recent_alerts[-3:]:
                report += f"  • {alert['message'][:60]}\n"
        
        report += f"{'━' * 35}"
        return report