import pytest
from unittest.mock import MagicMock


class FakeSessionManager:
    """Fake session manager for testing."""
    def __init__(self):
        self.sent = []
        self.sessions = {}
        self.active_session_id = None

    def create_session(self, user_id, template_name, work_dir, session_name):
        session = MagicMock()
        session.session_id = f"s_{len(self.sessions) + 1:03d}"
        session.user_id = user_id
        session.template_name = template_name
        session.work_dir = work_dir
        session.session_name = session_name
        session.status = "running"
        session.last_input = None
        self.sessions[session.session_id] = session
        self.active_session_id = session.session_id
        return session

    def get_active_session(self, user_id):
        if self.active_session_id:
            return self.sessions.get(self.active_session_id)
        return None

    def send_to_active_session(self, user_id, content):
        self.sent.append((user_id, self.active_session_id, content))
        session = self.get_active_session(user_id)
        if session:
            session.last_input = content
        return True

    def send_to_session(self, user_id, session_id, content):
        self.sent.append((user_id, session_id, content))
        session = self.sessions.get(session_id)
        if session:
            session.last_input = content
            return True
        return False

    def get_pool_info(self, user_id):
        return {
            "session_count": len(self.sessions),
            "active_session_id": self.active_session_id,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "session_name": s.session_name,
                    "template_name": s.template_name,
                    "status": s.status,
                }
                for s in self.sessions.values()
            ],
        }

    def list_sessions(self, user_id):
        return list(self.sessions.values())


class FakeFeishuBot:
    """Fake Feishu bot for testing."""
    def __init__(self):
        self.sent_messages = []

    def send_text(self, text):
        self.sent_messages.append(text)


class FakeMonitor:
    """Fake monitor for testing."""
    def __init__(self):
        self.alerts = []

    def record_command(self, command):
        pass

    def get_status_report(self):
        return "Fake status report"

    def set_alert_callback(self, callback):
        pass


def test_plain_message_routes_to_active_session():
    """Test that plain messages route to active session."""
    # Import here to ensure fresh module
    import sys
    sys.path.insert(0, 'src')
    from main import AgentBridgeService

    # Create a mock config
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
feishu:
  app_id: "test"
  app_secret: "test"
  connection_mode: "websocket"
  server_port: 9980
  allowed_users: []
agent:
  default: "claude_code"
  default_timeout: 30
  max_sessions_per_user: 5
  allowed_work_roots: ["E:/test"]
  templates:
    claude_code:
      command: "claude"
      args: []
      env: {}
monitor:
  check_interval: 5
  timeout_threshold: 300
  heartbeat_interval: 60
output_filter:
  enabled: false
""")
        config_path = f.name

    try:
        service = AgentBridgeService(config_path=config_path)
        service.session_manager = FakeSessionManager()
        service.feishu_bot = FakeFeishuBot()
        service.monitor = FakeMonitor()

        # Create a session for user_a
        session = service.session_manager.create_session("user_a", "claude_code", "E:/test", "test")

        # Send a plain message
        service._handle_feishu_message("user_a", "fix login bug")

        # Verify it was routed to active session
        assert len(service.session_manager.sent) == 1
        assert service.session_manager.sent[0] == ("user_a", session.session_id, "fix login bug")
    finally:
        os.unlink(config_path)


def test_session_command_routed_to_handler():
    """Test that /session commands are handled as system commands."""
    import sys
    sys.path.insert(0, 'src')
    from main import AgentBridgeService

    import tempfile
    import os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
feishu:
  app_id: "test"
  app_secret: "test"
  connection_mode: "websocket"
  server_port: 9980
  allowed_users: []
agent:
  default: "claude_code"
  default_timeout: 30
  max_sessions_per_user: 5
  allowed_work_roots: ["E:/test"]
  templates:
    claude_code:
      command: "claude"
      args: []
      env: {}
monitor:
  check_interval: 5
  timeout_threshold: 300
  heartbeat_interval: 60
output_filter:
  enabled: false
""")
        config_path = f.name

    try:
        service = AgentBridgeService(config_path=config_path)
        service.session_manager = FakeSessionManager()
        service.feishu_bot = FakeFeishuBot()
        service.monitor = FakeMonitor()

        # Create a session first
        service.session_manager.create_session("user_a", "claude_code", "E:/test", "test")

        # Send a system command - should be handled as system, not routed to session
        service._handle_feishu_message("user_a", "/session list")

        # Should NOT have been sent to session (it's a system command)
        assert len(service.session_manager.sent) == 0
    finally:
        os.unlink(config_path)


def test_directed_message_with_session_id():
    """Test that @sid: directed messages include session_id metadata."""
    import sys
    sys.path.insert(0, 'src')
    from main import AgentBridgeService
    from feishu.message_handler import MessageHandler

    import tempfile
    import os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
feishu:
  app_id: "test"
  app_secret: "test"
  connection_mode: "websocket"
  server_port: 9980
  allowed_users: []
agent:
  default: "claude_code"
  default_timeout: 30
  max_sessions_per_user: 5
  allowed_work_roots: ["E:/test"]
  templates:
    claude_code:
      command: "claude"
      args: []
      env: {}
monitor:
  check_interval: 5
  timeout_threshold: 300
  heartbeat_interval: 60
output_filter:
  enabled: false
""")
        config_path = f.name

    try:
        service = AgentBridgeService(config_path=config_path)
        service.session_manager = FakeSessionManager()
        service.feishu_bot = FakeFeishuBot()
        service.monitor = FakeMonitor()

        # Create a session for user_a
        session = service.session_manager.create_session("user_a", "claude_code", "E:/test", "test")

        # Send a directed message
        service._handle_feishu_message("user_a", "@sid:s_001 fix login bug")

        # Should route to session s_001
        assert len(service.session_manager.sent) == 1
        user_id, session_id, content = service.session_manager.sent[0]
        assert content == "fix login bug"
    finally:
        os.unlink(config_path)
