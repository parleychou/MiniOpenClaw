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
from feishu.message_handler import MessageHandler
from agent.template_registry import TemplateRegistry
from agent.command_agent import CommandAgent
from session.manager import SessionManager
from monitor.status_monitor import StatusMonitor
from utils.logger import Logger

logger = Logger("main")


class AgentBridgeService:
    """飞书-Agent 桥接服务主控制器（多会话版本）"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config", "config.yaml"
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.session_manager = None
        self.feishu_bot = None
        self.monitor = None
        self.template_registry = None
        self._running = False
        self._lock = threading.Lock()

    def _create_agent_factory(self):
        """Create agent factory for SessionManager."""
        def create_agent(config, output_filter_config):
            """Factory function to create agents."""
            return CommandAgent(config, output_filter_config)
        return create_agent

    def start(self):
        """启动服务"""
        self._running = True
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"  飞书 Agent Bridge 服务 (多会话版)")
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

        # 1. 初始化模板注册表
        agent_config = self.config.get('agent', {})
        templates = agent_config.get('templates', {})
        if not templates:
            # Fallback to legacy config
            templates = {
                'claude_code': {
                    'command': agent_config.get('claude_code', {}).get('command', 'claude'),
                    'args': agent_config.get('claude_code', {}).get('args', []),
                    'env': {},
                },
                'opencode': {
                    'command': agent_config.get('opencode', {}).get('command', 'opencode'),
                    'args': agent_config.get('opencode', {}).get('args', []),
                    'env': {},
                },
            }

        self.template_registry = TemplateRegistry(
            templates=templates,
            allowed_work_roots=agent_config.get('allowed_work_roots', []),
            max_sessions_per_user=agent_config.get('max_sessions_per_user', 5),
        )

        # 2. 初始化会话管理器
        self.session_manager = SessionManager(
            template_registry=self.template_registry,
            agent_factory=self._create_agent_factory(),
            store=None,
        )
        print(f"{Fore.GREEN}[OK] 会话管理器已初始化{Style.RESET_ALL}")

        # 3. 初始化监控（不绑定特定agent）
        self.monitor = StatusMonitor(self.config['monitor'], None)
        self.monitor.start()

        # 4. 初始化飞书机器人
        self.feishu_bot = FeishuBot(
            config=self.config['feishu'],
            agent=None,  # 不再直接使用agent
            monitor=self.monitor,
            on_message=self._handle_feishu_message
        )

        # 设置监控告警回调
        self.monitor.set_alert_callback(self.feishu_bot.send_text)

        # 5. 启动飞书事件监听
        feishu_thread = threading.Thread(target=self.feishu_bot.start, daemon=True)
        feishu_thread.start()

        # 6. 通知飞书服务已启动
        startup_info = (
            f"[OK] Agent Bridge 服务已启动 (多会话版)\n"
            f"模板: {', '.join(self.template_registry.list_templates())}\n"
            f"最大会话/用户: {self.template_registry.max_sessions_per_user}"
        )
        self.feishu_bot.send_text(startup_info)

        print(f"{Fore.GREEN}[OK] 服务启动完成，等待飞书消息...{Style.RESET_ALL}\n")
        print(f"{Fore.YELLOW}控制台命令:{Style.RESET_ALL}")
        print(f"  /status  - 查看当前状态")
        print(f"  /help    - 帮助信息\n")

        # 7. 控制台输入循环
        self._console_loop()

    def _handle_feishu_message(self, user_id: str, message: str, chat_id: str = None):
        """处理来自飞书的消息"""
        logger.info(f"收到飞书消息 [{user_id}]: {message}")

        # 如果提供了 chat_id，存储它用于回复
        if chat_id:
            self.feishu_bot._current_chat_id = chat_id

        # 使用 MessageHandler 解析消息
        parsed = MessageHandler.parse_message(message)

        msg_type = parsed.get("type")
        content = parsed.get("content")
        metadata = parsed.get("metadata", {})

        # 系统命令
        if msg_type == "system":
            self._handle_command(user_id, content, source="feishu")
            return

        # 定向会话消息
        target_session_id = metadata.get("session_id")

        if target_session_id:
            # 发送到指定会话
            success = self.session_manager.send_to_session(
                user_id=user_id,
                session_id=target_session_id,
                content=content,
            )
            if not success:
                self.feishu_bot.send_text(f"[!] 会话 {target_session_id} 不存在")
            return

        # 发送到活动会话
        active_session = self.session_manager.get_active_session(user_id)
        if not active_session:
            self.feishu_bot.send_text(
                "[!] 没有活动会话\n"
                "请使用 /session new <模板> <路径> [名称] 创建新会话"
            )
            return

        success = self.session_manager.send_to_active_session(user_id, content)
        if success:
            logger.info(f"消息已发送到活动会话 {active_session.session_id}")
        else:
            self.feishu_bot.send_text("[!] 发送失败，请稍后重试")

    def _handle_command(self, user_id: str, command: str, source: str = "console"):
        """处理系统命令"""
        cmd = command.strip().lower()
        parts = command.strip().split()
        base_cmd = parts[0].lower() if parts else ""

        # /template 命令
        if base_cmd == "/template":
            self._handle_template_command(user_id, command, source)
            return

        # /session 命令
        if base_cmd == "/session":
            self._handle_session_command(user_id, command, source)
            return

        # 通用命令
        if cmd == "/status":
            self._handle_status_command(user_id, source)
        elif cmd == "/stop":
            self.stop()
        elif cmd == "/help":
            self._handle_help_command(user_id, source)
        else:
            msg = f"未知命令: {command}\n使用 /help 查看可用命令"
            if source == "feishu":
                self.feishu_bot.send_text(msg)
            else:
                print(msg)

    def _handle_template_command(self, user_id: str, command: str, source: str):
        """处理 /template 命令"""
        parts = command.strip().split()
        if len(parts) < 2:
            self.feishu_bot.send_text("[!] 用法: /template list | /template show <名称>")
            return

        sub_cmd = parts[1].lower()

        if sub_cmd == "list":
            templates = self.template_registry.list_templates()
            msg = "📋 可用模板:\n"
            for t in templates:
                template = self.template_registry.get_template(t)
                cmd = template.get('command', 'N/A')
                msg += f"  • {t}: {cmd}\n"
            self.feishu_bot.send_text(msg)
        elif sub_cmd == "show" and len(parts) >= 3:
            tpl_name = parts[2]
            template = self.template_registry.get_template(tpl_name)
            if template:
                msg = f"📦 模板: {tpl_name}\n"
                msg += f"  命令: {template.get('command', 'N/A')}\n"
                msg += f"  参数: {template.get('args', [])}\n"
                self.feishu_bot.send_text(msg)
            else:
                self.feishu_bot.send_text(f"[!] 模板 {tpl_name} 不存在")
        else:
            self.feishu_bot.send_text("[!] 用法: /template list | /template show <名称>")

    def _handle_session_command(self, user_id: str, command: str, source: str):
        """处理 /session 命令"""
        parts = command.strip().split()
        if len(parts) < 2:
            self.feishu_bot.send_text(
                "[!] 用法:\n"
                "/session new <模板> <路径> [名称]\n"
                "/session list\n"
                "/session use <会话ID>\n"
                "/session info <会话ID>\n"
                "/session stop <会话ID>\n"
                "/session restart <会话ID>\n"
                "/session rm <会话ID>"
            )
            return

        sub_cmd = parts[1].lower()

        if sub_cmd == "new":
            if len(parts) < 4:
                self.feishu_bot.send_text("[!] 用法: /session new <模板> <路径> [名称]")
                return
            template_name = parts[2]
            work_dir = parts[3]
            session_name = parts[4] if len(parts) >= 5 else template_name

            # 验证模板存在
            if not self.template_registry.get_template(template_name):
                self.feishu_bot.send_text(f"[!] 模板 {template_name} 不存在")
                return

            # 验证路径
            if not self.template_registry.validate_work_dir(work_dir):
                self.feishu_bot.send_text(f"[!] 路径 {work_dir} 不在允许范围内")
                return

            # 检查会话数限制
            pool_info = self.session_manager.get_pool_info(user_id)
            if pool_info["session_count"] >= self.template_registry.max_sessions_per_user:
                self.feishu_bot.send_text(
                    f"[!] 会话数已达上限 ({self.template_registry.max_sessions_per_user})，"
                    "请先关闭一些会话"
                )
                return

            # 创建会话
            session = self.session_manager.create_session(
                user_id=user_id,
                template_name=template_name,
                work_dir=work_dir,
                session_name=session_name,
            )
            self.feishu_bot.send_text(
                f"✅ 会话已创建: {session.session_id}\n"
                f"模板: {template_name}\n"
                f"目录: {work_dir}\n"
                f"名称: {session_name}"
            )

        elif sub_cmd == "list":
            pool_info = self.session_manager.get_pool_info(user_id)
            sessions = pool_info.get("sessions", [])
            if not sessions:
                self.feishu_bot.send_text("暂无会话，使用 /session new 创建")
                return

            msg = "📋 会话列表:\n"
            for s in sessions:
                active = " ◀️" if s["session_id"] == pool_info.get("active_session_id") else ""
                msg += f"  • {s['session_id']} ({s['session_name']}) - {s['status']}{active}\n"
            self.feishu_bot.send_text(msg)

        elif sub_cmd == "use" and len(parts) >= 3:
            session_id = parts[2]
            success = self.session_manager.set_active_session(user_id, session_id)
            if success:
                self.feishu_bot.send_text(f"✅ 已切换到会话 {session_id}")
            else:
                self.feishu_bot.send_text(f"[!] 会话 {session_id} 不存在")

        elif sub_cmd == "info" and len(parts) >= 3:
            session_id = parts[2]
            session = self.session_manager.get_session(user_id, session_id)
            if not session:
                self.feishu_bot.send_text(f"[!] 会话 {session_id} 不存在")
            else:
                msg = (
                    f"📦 会话详情: {session.session_id}\n"
                    f"  名称: {session.session_name}\n"
                    f"  模板: {session.template_name}\n"
                    f"  目录: {session.work_dir}\n"
                    f"  状态: {session.status}\n"
                    f"  创建: {session.created_at}"
                )
                self.feishu_bot.send_text(msg)

        elif sub_cmd == "stop" and len(parts) >= 3:
            session_id = parts[2]
            success = self.session_manager.stop_session(user_id, session_id)
            if success:
                self.feishu_bot.send_text(f"✅ 会话 {session_id} 已停止")
            else:
                self.feishu_bot.send_text(f"[!] 会话 {session_id} 不存在")

        elif sub_cmd == "restart" and len(parts) >= 3:
            session_id = parts[2]
            success = self.session_manager.restart_session(user_id, session_id)
            if success:
                self.feishu_bot.send_text(f"✅ 会话 {session_id} 已重启")
            else:
                self.feishu_bot.send_text(f"[!] 会话 {session_id} 不存在")

        elif sub_cmd == "rm" and len(parts) >= 3:
            session_id = parts[2]
            success = self.session_manager.remove_session(user_id, session_id)
            if success:
                self.feishu_bot.send_text(f"✅ 会话 {session_id} 已删除")
            else:
                self.feishu_bot.send_text(f"[!] 会话 {session_id} 不存在")
        else:
            self.feishu_bot.send_text("[!] 用法: /session list | new | use | info | stop | restart | rm")

    def _handle_status_command(self, user_id: str, source: str):
        """处理 /status 命令"""
        pool_info = self.session_manager.get_pool_info(user_id)
        sessions = pool_info.get("sessions", [])
        active_id = pool_info.get("active_session_id")

        msg = f"📊 状态报告\n{'━' * 30}\n"
        msg += f"会话数: {pool_info['session_count']}/{self.template_registry.max_sessions_per_user}\n"

        if sessions:
            msg += "会话:\n"
            for s in sessions:
                active = " ◀️" if s["session_id"] == active_id else ""
                msg += f"  • {s['session_id']} ({s['session_name']}) - {s['status']}{active}\n"
        else:
            msg += "无活动会话\n"

        if source == "feishu":
            self.feishu_bot.send_text(msg)
        else:
            print(msg)

    def _handle_help_command(self, user_id: str, source: str):
        """处理 /help 命令"""
        help_text = (
            "📋 可用命令:\n"
            "━" * 30 + "\n"
            "/template list - 列出模板\n"
            "/template show <名称> - 查看模板详情\n"
            "━" * 30 + "\n"
            "/session new <模板> <路径> [名称] - 创建会话\n"
            "/session list - 列出会话\n"
            "/session use <会话ID> - 切换会话\n"
            "/session info <会话ID> - 会话详情\n"
            "/session stop <会话ID> - 停止会话\n"
            "/session restart <会话ID> - 重启会话\n"
            "/session rm <会话ID> - 删除会话\n"
            "━" * 30 + "\n"
            "@sid:<会话ID> <消息> - 定向发送\n"
            "━" * 30 + "\n"
            "/status - 状态\n"
            "/stop - 停止服务\n"
            "/help - 帮助"
        )
        if source == "feishu":
            self.feishu_bot.send_text(help_text)
        else:
            print(help_text)

    def _console_loop(self):
        """控制台输入循环"""
        try:
            while self._running:
                try:
                    user_input = input()
                    if user_input.startswith('/'):
                        self._handle_command("console", user_input, source="console")
                    else:
                        print("控制台不支持直接发送消息，请使用飞书")
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
            self.feishu_bot.send_text("[STOP] Agent Bridge 服务已停止")

        if self.monitor:
            self.monitor.stop()

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
