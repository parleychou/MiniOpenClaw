# src/feishu/message_handler.py
import re
import json
from typing import Optional


class MessageHandler:
    """
    飞书消息智能处理器
    解析用户意图，转换为Agent可理解的命令
    """

    # 快捷命令映射
    QUICK_COMMANDS = {
        '确认': 'y',
        '同意': 'y',
        '是': 'y',
        '好的': 'y',
        'ok': 'y',
        '拒绝': 'n',
        '否': 'n',
        '取消': 'n',
        '状态': '/status',
        '帮助': '/help',
        '重启': '/restart',
        '停止': '/stop',
    }

    # @sid: directed message pattern
    DIRECTED_SESSION_PATTERN = re.compile(
        r'^@sid:(?P<session_id>[A-Za-z0-9_-]+)\s+(?P<content>.+)$'
    )

    @classmethod
    def parse_message(cls, text: str) -> dict:
        """
        解析飞书消息
        Returns:
            {
                "type": "command" | "agent_input" | "system",
                "content": str,
                "metadata": dict
            }
        """
        text = text.strip()

        # 首先检查原始文本中是否有 @sid: 模式
        directed_match = cls.DIRECTED_SESSION_PATTERN.match(text)
        if directed_match:
            return {
                "type": "agent_input",
                "content": directed_match.group("content").strip(),
                "metadata": {"session_id": directed_match.group("session_id")},
            }

        # 去除飞书@机器人的文本（但保留@sid:模式 - 使用负向预查）
        # Pattern matches @xxx where xxx is NOT "sid"
        text = re.sub(r'@(?!sid:)(\w+)\s*', '', text).strip()

        # 去除后再次检查是否有 @sid: 模式
        directed_match = cls.DIRECTED_SESSION_PATTERN.match(text)
        if directed_match:
            return {
                "type": "agent_input",
                "content": directed_match.group("content").strip(),
                "metadata": {"session_id": directed_match.group("session_id")},
            }

        # 快捷命令
        lower_text = text.lower()
        if lower_text in cls.QUICK_COMMANDS:
            mapped = cls.QUICK_COMMANDS[lower_text]
            if mapped.startswith('/'):
                return {"type": "system", "content": mapped, "metadata": {}}
            else:
                return {"type": "agent_input", "content": mapped, "metadata": {"quick": True}}

        # 系统命令
        if text.startswith('/'):
            return {"type": "system", "content": text, "metadata": {}}

        # 多行命令（代码块）
        code_match = re.search(r'```(?:\w+)?\n?(.*?)```', text, re.DOTALL)
        if code_match:
            return {
                "type": "agent_input",
                "content": code_match.group(1).strip(),
                "metadata": {"is_code_block": True}
            }

        # 普通Agent输入
        return {"type": "agent_input", "content": text, "metadata": {}}

    @classmethod
    def format_status(cls, status: dict) -> str:
        """格式化状态信息为飞书消息"""
        uptime = int(status.get('uptime', 0))
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        idle_time = int(status.get('idle_time', 0))

        status_emoji = {
            'running': '🟢',
            'stopped': '🔴',
            'processing': '🔵',
            'waiting_confirm': '🟡',
        }

        s = status.get('status', 'unknown')
        emoji = status_emoji.get(s, '⚪')

        return (
            f"📊 Agent 状态报告\n"
            f"{'─' * 30}\n"
            f"状态: {emoji} {s}\n"
            f"类型: {status.get('agent_type', 'N/A')}\n"
            f"工作目录: {status.get('work_dir', 'N/A')}\n"
            f"运行时间: {uptime_str}\n"
            f"执行命令数: {status.get('command_count', 0)}\n"
            f"当前阶段: {status.get('filter_state', 'N/A')}\n"
            f"空闲时间: {idle_time}s\n"
            f"{'─' * 30}"
        )
