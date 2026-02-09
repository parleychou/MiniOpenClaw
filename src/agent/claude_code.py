from agent.base import BaseAgent


class ClaudeCodeAgent(BaseAgent):
    """Claude Code Agent适配器"""

    def __init__(self, config: dict, filter_config: dict):
        super().__init__(config, filter_config)
        self.init_filter(filter_config)
        
        # Claude Code 特定的确认模式
        if self._output_filter:
            import re
            self._output_filter.confirm_patterns.extend([
                re.compile(r'Do you want to proceed', re.IGNORECASE),
                re.compile(r'Allow this action', re.IGNORECASE),
                re.compile(r'Approve|Reject', re.IGNORECASE),
                re.compile(r'Would you like me to', re.IGNORECASE),
            ])
            self._output_filter.result_patterns.extend([
                re.compile(r'I\'ve (created|modified|updated|deleted|written)', re.IGNORECASE),
                re.compile(r'Changes saved', re.IGNORECASE),
                re.compile(r'Task completed', re.IGNORECASE),
            ])

    def start(self) -> bool:
        """启动Claude Code"""
        # Claude Code 特定启动逻辑
        # 确保使用 --dangerously-skip-permissions 或其他必要参数
        return super().start()

    def send_input(self, text: str):
        """发送输入（支持Claude Code特定命令）"""
        # 转换简写命令
        cmd_map = {
            'y': 'y',
            'n': 'n',
            'yes': 'yes',
            'no': 'no',
        }
        
        mapped = cmd_map.get(text.lower(), text)
        super().send_input(mapped)