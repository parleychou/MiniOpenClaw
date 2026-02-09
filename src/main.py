# src/main.py
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
from agent.claude_code import ClaudeCodeAgent
from agent.opencode import OpenCodeAgent
from monitor.status_monitor import StatusMonitor
from utils.logger import Logger

logger = Logger("main")


class AgentBridgeService:
    """飞书-Agent 桥接服务主控制器"""

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
        print(f"  飞书 Agent Bridge 服务")
        print(f"{'='*60}{Style.RESET_ALL}\n")

        # 显示配置信息
        feishu_config = self.config.get('feishu', {})
        print(f"{Fore.CYAN}飞书配置:{Style.RESET_ALL}")
        print(f"   App ID: {feishu_config.get('app_id', 'N/A')}")
        print(f"   连接模式: {feishu_config.get('connection_mode', 'webhook')}")
        print(f"   服务端口: {feishu_config.get('server_port', 9980)}")
        allowed = feishu_config.get('allowed_users', [])
        if allowed:
            print(f"   允许用户: {', '.join(allowed)}")
        else:
            print(f"   {Fore.YELLOW}允许用户: 所有用户 (建议从日志获取 OpenID 后配置){Style.RESET_ALL}")
        
        if feishu_config.get('connection_mode') == 'webhook':
            print(f"\n{Fore.YELLOW}Webhook 模式需要公网访问:{Style.RESET_ALL}")
            print(f"   1. 启动 ngrok: ngrok http {feishu_config.get('server_port', 9980)}")
            print(f"   2. 配置飞书 Webhook URL: https://your-ngrok-url/feishu/event")
            print(f"   3. 或在飞书开放平台选择'长连接'模式")
        print()

        # 1. 初始化Agent（但不启动）
        self._init_agent(start_agent=False)

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

        # 3.5 设置监控告警回调（将告警发送到飞书）
        self.monitor.set_alert_callback(self.feishu_bot.send_text)
        
        # 3.6 确保 Agent 的飞书回调已设置
        if self.agent:
            self.agent.set_feishu_callback(self.feishu_bot._on_agent_output)
            logger.info(f"[INIT] Agent 飞书回调已设置")
            
        # 3.7 现在启动 Agent
        if self.agent:
            success = self.agent.start()
            if success:
                print(f"{Fore.GREEN}[OK] Agent 进程已启动{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}[!] Agent 进程启动失败，Web服务将继续运行{Style.RESET_ALL}")

        # 4. 启动飞书事件监听（启动HTTP服务器接收回调）
        feishu_thread = threading.Thread(target=self.feishu_bot.start, daemon=True)
        feishu_thread.start()

        # 5. 通知飞书服务已启动
        agent_info = f"当前Agent: {self.config['agent']['default']}\n"
        if self.agent:
            agent_info += f"工作目录: {self.agent.work_dir}"
        else:
            agent_info += "Agent状态: 未运行"
        self.feishu_bot.send_text(f"[OK] Agent Bridge 服务已启动\n{agent_info}")

        print(f"{Fore.GREEN}[OK] 服务启动完成，等待飞书消息...{Style.RESET_ALL}\n")
        print(f"{Fore.YELLOW}控制台命令:{Style.RESET_ALL}")
        print(f"  /status  - 查看当前状态")
        print(f"  /switch  - 切换Agent")
        print(f"  /stop    - 停止服务")
        print(f"  /help    - 帮助信息\n")

        # 6. 控制台输入循环
        self._console_loop()

    def _init_agent(self, start_agent=True):
        """初始化Agent"""
        agent_type = self.config['agent']['default']
        agent_config = self.config['agent'][agent_type]

        try:
            if agent_type == 'claude_code':
                self.agent = ClaudeCodeAgent(agent_config, self.config['output_filter'])
            elif agent_type == 'opencode':
                self.agent = OpenCodeAgent(agent_config, self.config['output_filter'])
            else:
                raise ValueError(f"未知的Agent类型: {agent_type}")

            print(f"{Fore.GREEN}[OK] Agent [{agent_type}] 初始化完成{Style.RESET_ALL}")
            
            if start_agent:
                success = self.agent.start()
                if success:
                    print(f"{Fore.GREEN}[OK] Agent 进程已启动{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}[!] Agent 进程启动失败，Web服务将继续运行{Style.RESET_ALL}")
                    self.agent = None
        except Exception as e:
            print(f"{Fore.YELLOW}[!] Agent 初始化失败: {e}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[!] Web服务将继续运行，但Agent功能不可用{Style.RESET_ALL}")
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
                logger.error("Agent 未初始化")
                self.feishu_bot.send_text("[!] Agent 未初始化")
                return
            
            is_running = self.agent.is_running()
            logger.info(f"Agent 运行状态: {is_running}")
            
            if is_running:
                # 更新监控状态
                self.monitor.record_command(message)
                # 发送到Agent
                logger.info(f"发送消息到 Agent: {message}")
                self.agent.send_input(message)
            else:
                logger.warning("Agent 未运行")
                agent_status = self.agent.get_status()
                logger.warning(f"Agent 状态: {agent_status}")
                self.feishu_bot.send_text(f"[!] Agent未运行，状态: {agent_status.get('status', 'unknown')}\n请使用 /restart 重启")

    def _handle_command(self, command: str, source: str = "console"):
        """处理系统命令"""
        cmd = command.strip().lower()

        if cmd == '/status':
            status = self.monitor.get_status_report()
            if source == "feishu":
                self.feishu_bot.send_text(status)
            else:
                print(status)

        elif cmd == '/switch':
            current = self.config['agent']['default']
            new_agent = 'opencode' if current == 'claude_code' else 'claude_code'
            self._switch_agent(new_agent)
            msg = f"🔄 已切换到 {new_agent}"
            if source == "feishu":
                self.feishu_bot.send_text(msg)
            print(msg)

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
                "/switch - 切换Agent (claude_code/opencode)\n"
                "/restart - 重启当前Agent\n"
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

    def _switch_agent(self, agent_type: str):
        """切换Agent"""
        with self._lock:
            if self.agent:
                self.agent.stop()
            self.config['agent']['default'] = agent_type
            self._init_agent()
            self.monitor.agent = self.agent
            # 重新设置飞书回调
            if self.agent and self.feishu_bot:
                self.agent.set_feishu_callback(self.feishu_bot._on_agent_output)

    def _restart_agent(self):
        """重启Agent"""
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
        import time
        try:
            while self._running:
                try:
                    user_input = input()
                    if user_input.startswith('/'):
                        self._handle_command(user_input, source="console")
                    else:
                        # 控制台直接输入也发送到Agent
                        if self.agent and self.agent.is_running():
                            self.agent.send_input(user_input)
                except EOFError:
                    # 在非交互式环境中，控制台输入已关闭
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
            self.feishu_bot.send_text("[STOP] Agent Bridge 服务已停止")

        if self.monitor:
            self.monitor.stop()

        if self.agent:
            self.agent.stop()

        print(f"{Fore.GREEN}[OK] 服务已停止{Style.RESET_ALL}")
        sys.exit(0)


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    service = AgentBridgeService(config_path)

    # 注册信号处理
    signal.signal(signal.SIGINT, lambda s, f: service.stop())
    signal.signal(signal.SIGTERM, lambda s, f: service.stop())

    service.start()


if __name__ == "__main__":
    main()
