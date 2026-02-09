# src/terminal/__init__.py
from .pty_manager import PTYManager, WinPTYManager

__all__ = ['PTYManager', 'WinPTYManager']
