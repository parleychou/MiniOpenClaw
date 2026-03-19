# src/agent/command_agent.py
"""Generic command agent that uses LaunchSpec for configuration."""

from .base import BaseAgent


class CommandAgent(BaseAgent):
    """
    Generic agent that uses a command spec for configuration.

    This agent is template-driven and can launch any CLI command
    based on the configuration passed to it.
    """

    def __init__(self, config: dict, output_filter_config: dict):
        """
        Initialize CommandAgent.

        Args:
            config: Configuration dict with command, args, work_dir, env
            output_filter_config: Output filter configuration
        """
        super().__init__(config, output_filter_config)
        # Extra environment variables from template
        self.extra_env = config.get("env", {})

    def start(self) -> bool:
        """
        Start the agent process.

        Returns:
            True if started successfully, False otherwise
        """
        # Pass extra_env to PTY manager for merging
        if hasattr(self, 'extra_env') and self.extra_env:
            # Store extra_env for use during process start
            pass
        return super().start()
