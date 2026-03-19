# src/agent/__init__.py
from .base import BaseAgent
from .claude_code import ClaudeCodeAgent
from .opencode import OpenCodeAgent
from .output_filter import OutputFilter
from .template_registry import TemplateRegistry, LaunchSpec

__all__ = ['BaseAgent', 'ClaudeCodeAgent', 'OpenCodeAgent', 'OutputFilter', 'TemplateRegistry', 'LaunchSpec']
