import pytest
from feishu.message_handler import MessageHandler


def test_parse_session_new_command():
    """Test parsing /session new command."""
    result = MessageHandler.parse_message("/session new codex E:\\repo\\api api-fix")

    assert result["type"] == "system"
    assert result["content"] == "/session new codex E:\\repo\\api api-fix"


def test_parse_directed_session_message():
    """Test parsing @sid: directed session messages."""
    result = MessageHandler.parse_message("@sid:s_002 fix the failing tests")

    assert result["type"] == "agent_input"
    assert result["metadata"]["session_id"] == "s_002"
    assert result["content"] == "fix the failing tests"


def test_parse_plain_message():
    """Test parsing regular messages."""
    result = MessageHandler.parse_message("Hello world")

    assert result["type"] == "agent_input"
    assert result["content"] == "Hello world"
    assert "session_id" not in result.get("metadata", {})


def test_parse_template_commands():
    """Test parsing template commands."""
    result = MessageHandler.parse_message("/template list")

    assert result["type"] == "system"
    assert result["content"] == "/template list"


def test_parse_status_command():
    """Test parsing /status command."""
    result = MessageHandler.parse_message("/status")

    assert result["type"] == "system"
    assert result["content"] == "/status"


def test_parse_help_command():
    """Test parsing /help command."""
    result = MessageHandler.parse_message("/help")

    assert result["type"] == "system"
    assert result["content"] == "/help"


def test_parse_quick_commands():
    """Test parsing quick commands."""
    # Chinese yes
    result = MessageHandler.parse_message("是")
    assert result["type"] == "agent_input"
    assert result["content"] == "y"

    # English ok
    result = MessageHandler.parse_message("ok")
    assert result["type"] == "agent_input"
    assert result["content"] == "y"

    # Status quick command
    result = MessageHandler.parse_message("状态")
    assert result["type"] == "system"
    assert result["content"] == "/status"


def test_parse_at_mention_stripped():
    """Test that @mention is stripped from message."""
    result = MessageHandler.parse_message("@bot_user 你好")

    assert result["type"] == "agent_input"
    assert result["content"] == "你好"


def test_parse_directed_with_at_mention():
    """Test @sid: with @mention prefix."""
    result = MessageHandler.parse_message("@bot @sid:s_003 hello")

    assert result["type"] == "agent_input"
    assert result["metadata"]["session_id"] == "s_003"
    assert result["content"] == "hello"


def test_parse_session_list_command():
    """Test parsing /session list command."""
    result = MessageHandler.parse_message("/session list")

    assert result["type"] == "system"
    assert result["content"] == "/session list"


def test_parse_session_info_command():
    """Test parsing /session info command."""
    result = MessageHandler.parse_message("/session info s_001")

    assert result["type"] == "system"
    assert result["content"] == "/session info s_001"
