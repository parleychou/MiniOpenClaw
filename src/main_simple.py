# src/main_simple.py
"""
简化版主程序 - 使用新的简单实现
"""
import sys
import os
import signal
import threading
import yaml
from colorama import init, Fore, Style

# Windows 控制台颜色支持
init(autoreset=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from feishu.bot import FeishuBot
from agent.simple_agent import SimpleAgent
from monitor.status_monitor import StatusMonitor
from utils.logger import Logger

logger = Logger("main")


class SimpleBridgeService:
    """简化的飞书-Agent 桥接服务"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config", "config.yaml"
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.agent = None
        self.feishu_bot = None
        self.monitor = None
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        """启动服务"""
        self._running = True
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"  飞书 Agent Bridge 服务 (简化版)")
        print(f"{'='*60}{Style.RESET_ALL}\n")

        # 显示配置信息
        feishu_config = self.config.get('feishu', {})
        print(f"{Fore.CYAN}飞书配置:{Style.RESET_ALL}")
        print(f"   App ID: {feishu_config.get('app_id', 'N/A')}")
        print(f"   连接模式: {feishu_config.get('connection_mode', 'webhook')}")
        print(f"   服务端口: {feishu_config.get('server_port', 9980)}")
        print()

        # 1. 初始化 Agent
        self._init_agent()

        # 2. 初始化监控
        self.monitor = StatusMonitor(self.config['monitor'], self.agent)
        self.monitor.start()

        # 3. 初始化飞书机器人
        self.feishu_bot = FeishuBot(
            config=self.config['feishu'],
            agent=self.agent,
            monitor=self.monitor,
            on_message=self._handle_feishu_message
        )

        # 4. 设置监控告警回调
        self.monitor.set_alert_callback(self.feishu_bot.send_text)
        
        # 5. 设置 Agent 的飞书回调
        if self.agent:
            self.agent.set_feishu_callback(self.feishu_bot._on_agent_output)
            logger.info("✅ Agent 飞书回调已设置")

        # 6. 启动飞书事件监听
        feishu_thread = threading.Thread(target=self.feishu_bot.start, daemon=True)
        feishu_thread.start()

        # 7. 通知飞书服务已启动
        agent_info = f"当前Agent: {self.config['agent']['default']}\n"
        if self.agent:
            agent_info += f"工作目录: {self.agent.work_dir}"
        else:
            agent_info += "Agent状态: 未运行"
        self.feishu_bot.send_text(f"✅ Agent Bridge 服务已启动\n{agent_info}")

        print(f"{Fore.GREEN}✅ 服务启动完成，等待飞书消息...{Style.RESET_ALL}\n")
        print(f"{Fore.YELLOW}控制台命令:{Style.RESET_ALL}")
        print(f"  /status  - 查看当前状态")
        print(f"  /restart - 重启Agent")
        print(f"  /stop    - 停止服务")
        print(f"  /help    - 帮助信息\n")

        # 8. 控制台输入循环
        self._console_loop()

    def _init_agent(self):
        """初始化 Agent"""
        agent_type = self.config['agent']['default']
        agent_config = self.config['agent'][agent_type]

        try:
            self.agent = SimpleAgent(agent_config)
            print(f"{Fore.GREEN}✅ Agent [{agent_type}] 初始化完成{Style.RESET_ALL}")
            
            success = self.agent.start()
            if success:
                print(f"{Fore.GREEN}✅ Agent 进程已启动{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}⚠️ Agent 进程启动失败{Style.RESET_ALL}")
                self.agent = None
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Agent 初始化失败: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            self.agent = None

    def _handle_feishu_message(self, user_id: str, message: str):
        """处理来自飞书的消息"""
        logger.info(f"收到飞书消息 [{user_id}]: {message}")

        # 系统命令处理
        if message.startswith('/'):
            self._handle_command(message, source="feishu")
            return

        with self._lock:
            # 检查 Agent 状态
            if not self.agent:
                logger.error("❌ Agent 未初始化")
                self.feishu_bot.send_text("❌ Agent 未初始化")
                return
            
            is_running = self.agent.is_running()
            logger.info(f"Agent 运行状态: {is_running}")
            
            if is_running:
                # 更新监控状态
                self.monitor.record_command(message)
                # 发送到 Agent
                logger.info(f"📤 发送消息到 Agent: {message}")
                self.agent.send_input(message)
            else:
                logger.warning("⚠️ Agent 未运行")
                self.feishu_bot.send_text("⚠️ Agent未运行，请使用 /restart 重启")

    def _handle_command(self, command: str, source: str = "console"):
        """处理系统命令"""
        cmd = command.strip().lower()

        if cmd == '/status':
            status = self.monitor.get_status_report()
            if source == "feishu":
                self.feishu_bot.send_text(status)
            else:
                print(status)

        elif cmd == '/restart':
            self._restart_agent()
            msg = "🔄 Agent 已重启"
            if source == "feishu":
                self.feishu_bot.send_text(msg)
            print(msg)

        elif cmd == '/stop':
            self.stop()

        elif cmd == '/help':
            help_text = (
                "📋 可用命令:\n"
                "/status - 查看Agent状态\n"
                "/restart - 重启Agent\n"
                "/stop - 停止服务\n"
                "/help - 显示帮助"
            )
            if source == "feishu":
                self.feishu_bot.send_text(help_text)
            else:
                print(help_text)
        else:
            msg = f"未知命令: {command}"
            if source == "feishu":
                self.feishu_bot.send_text(msg)
            else:
                print(msg)

    def _restart_agent(self):
        """重启 Agent"""
        with self._lock:
            if self.agent:
                self.agent.stop()
            self._init_agent()
            self.monitor.agent = self.agent
            # 重新设置飞书回调
            if self.agent and self.feishu_bot:
                self.agent.set_feishu_callback(self.feishu_bot._on_agent_output)

    def _console_loop(self):
        """控制台输入循环"""
        try:
            while self._running:
                try:
                    user_input = input()
                    if user_input.startswith('/'):
                        self._handle_command(user_input, source="console")
                    else:
                        # 控制台直接输入也发送到 Agent
                        if self.agent and self.agent.is_running():
                            self.agent.send_input(user_input)
                except EOFError:
                    logger.info("控制台输入已关闭")
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """停止服务"""
        self._running = False
        print(f"\n{Fore.YELLOW}正在停止服务...{Style.RESET_ALL}")

        if self.feishu_bot:
            self.feishu_bot.send_text("🛑 Agent Bridge 服务已停止")

        if self.monitor:
            self.monitor.stop()

        if self.agent:
            self.agent.stop()

        print(f"{Fore.GREEN}✅ 服务已停止{Style.RESET_ALL}")
        sys.exit(0)


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    service = SimpleBridgeService(config_path)

    # 注册信号处理
    signal.signal(signal.SIGINT, lambda s, f: service.stop())
    signal.signal(signal.SIGTERM, lambda s, f: service.stop())

    service.start()


if __name__ == "__main__":
    main()
