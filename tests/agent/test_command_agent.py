import pytest
from agent.command_agent import CommandAgent


def test_command_agent_uses_launch_spec_values():
    """Test that CommandAgent uses config values correctly."""
    config = {
        "command": "codex",
        "args": ["--cwd", r"E:\2026\repo\api"],
        "work_dir": r"E:\2026\repo\api",
        "env": {"FEISHU_USER": "ou_123"},
    }
    agent = CommandAgent(config, {"enabled": False})

    assert agent.command == "codex"
    assert agent.args == ["--cwd", r"E:\2026\repo\api"]
    assert agent.work_dir == r"E:\2026\repo\api"
    assert agent.extra_env["FEISHU_USER"] == "ou_123"


def test_command_agent_extra_env():
    """Test that extra_env is properly extracted from config."""
    config = {
        "command": "test",
        "args": [],
        "work_dir": "/tmp",
        "env": {"KEY1": "val1", "KEY2": "val2"},
    }
    agent = CommandAgent(config, {})

    assert agent.extra_env == {"KEY1": "val1", "KEY2": "val2"}


def test_command_agent_no_env():
    """Test CommandAgent with no env in config."""
    config = {
        "command": "test",
        "args": ["arg1"],
        "work_dir": "/tmp",
    }
    agent = CommandAgent(config, {})

    assert agent.extra_env == {}
