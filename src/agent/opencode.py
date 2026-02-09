from agent.base import BaseAgent


class OpenCodeAgent(BaseAgent):
    """OpenCode Agent适配器"""

    def __init__(self, config: dict, filter_config: dict):
        super().__init__(config, filter_config)
        self.init_filter(filter_config)
        
        # OpenCode 特定模式
        if self._output_filter:
            import re
            self._output_filter.confirm_patterns.extend([
                re.compile(r'Apply changes\?', re.IGNORECASE),
                re.compile(r'Continue\?', re.IGNORECASE),
            ])

    def start(self) -> bool:
        """启动OpenCode"""
        return super().start()