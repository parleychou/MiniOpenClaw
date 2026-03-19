import pytest
from session.manager import SessionManager, AgentSession
from agent.template_registry import TemplateRegistry


def create_test_registry():
    """Create a TemplateRegistry for testing."""
    return TemplateRegistry(
        templates={
            "claude_code": {
                "command": "claude",
                "args": ["code"],
                "env": {},
                "append_prompt_as_stdin": True,
            },
            "opencode": {
                "command": "opencode",
                "args": [],
                "env": {},
                "append_prompt_as_stdin": True,
            },
            "codex": {
                "command": "codex",
                "args": [],
                "env": {},
                "append_prompt_as_stdin": True,
            },
        },
        allowed_work_roots=[r"E:\2026"],
        max_sessions_per_user=5,
    )


class FakeAgent:
    """Fake agent for testing session management."""
    def __init__(self, config=None, output_filter_config=None):
        self.messages = []
        self.running = True
        self.config = config
        self.output_filter_config = output_filter_config

    def start(self):
        return True

    def stop(self):
        self.running = False

    def is_running(self):
        return self.running

    def send_input(self, text):
        self.messages.append(text)

    def set_feishu_callback(self, callback):
        pass


def test_user_sessions_are_isolated():
    """Test that sessions are isolated by user_id."""
    manager = SessionManager(
        template_registry=create_test_registry(),
        agent_factory=lambda config, filter_config: FakeAgent(),
        store=None,
    )

    a = manager.create_session("user_a", "codex", r"E:\2026\repo\a", "a1")
    b = manager.create_session("user_b", "codex", r"E:\2026\repo\b", "b1")

    manager.set_active_session("user_a", a.session_id)
    manager.send_to_active_session("user_a", "fix api")

    # user_b's session should be isolated - last_input should be None
    assert manager.list_sessions("user_b")[0].session_id == b.session_id
    assert manager.get_session("user_b", b.session_id).last_input is None


def test_create_session_sets_status():
    """Test that created session has correct status."""
    manager = SessionManager(
        template_registry=create_test_registry(),
        agent_factory=lambda config, filter_config: FakeAgent(),
        store=None,
    )

    session = manager.create_session("user_a", "claude_code", r"E:\2026\repo", "test-session")

    assert session.status == "running"
    assert session.user_id == "user_a"
    assert session.template_name == "claude_code"
    assert session.work_dir == r"E:\2026\repo"
    assert session.session_name == "test-session"


def test_set_active_session():
    """Test setting active session."""
    manager = SessionManager(
        template_registry=create_test_registry(),
        agent_factory=lambda config, filter_config: FakeAgent(),
        store=None,
    )

    s1 = manager.create_session("user_a", "codex", r"E:\2026\repo\a", "session1")
    s2 = manager.create_session("user_a", "codex", r"E:\2026\repo\b", "session2")

    # Set s1 as active
    manager.set_active_session("user_a", s1.session_id)
    assert manager.get_active_session("user_a").session_id == s1.session_id

    # Switch to s2
    manager.set_active_session("user_a", s2.session_id)
    assert manager.get_active_session("user_a").session_id == s2.session_id


def test_send_to_active_session():
    """Test sending message to active session."""
    manager = SessionManager(
        template_registry=create_test_registry(),
        agent_factory=lambda config, filter_config: FakeAgent(),
        store=None,
    )

    session = manager.create_session("user_a", "codex", r"E:\2026\repo", "test")
    manager.set_active_session("user_a", session.session_id)

    manager.send_to_active_session("user_a", "hello world")

    assert len(session.agent.messages) == 1
    assert session.agent.messages[0] == "hello world"
    assert session.last_input == "hello world"


def test_list_sessions():
    """Test listing sessions for a user."""
    manager = SessionManager(
        template_registry=create_test_registry(),
        agent_factory=lambda config, filter_config: FakeAgent(),
        store=None,
    )

    s1 = manager.create_session("user_a", "codex", r"E:\2026\repo\a", "session1")
    s2 = manager.create_session("user_a", "codex", r"E:\2026\repo\b", "session2")
    _ = manager.create_session("user_b", "codex", r"E:\2026\repo\c", "session3")

    user_a_sessions = manager.list_sessions("user_a")
    user_b_sessions = manager.list_sessions("user_b")

    assert len(user_a_sessions) == 2
    assert len(user_b_sessions) == 1


def test_agent_session_model():
    """Test AgentSession dataclass fields."""
    session = AgentSession(
        session_id="s_001",
        user_id="user_123",
        template_name="codex",
        work_dir=r"E:\work",
        session_name="my-session",
        status="running",
    )

    assert session.session_id == "s_001"
    assert session.user_id == "user_123"
    assert session.template_name == "codex"
    assert session.work_dir == r"E:\work"
    assert session.session_name == "my-session"
    assert session.status == "running"
    assert session.last_input is None
    assert session.created_at is not None
