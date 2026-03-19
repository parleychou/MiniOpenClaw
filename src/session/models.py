# src/session/models.py
"""Session data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AgentSession:
    """
    Represents an agent session for a user.

    Attributes:
        session_id: Unique session identifier
        user_id: Feishu user ID who owns this session
        template_name: Name of the template used for this session
        work_dir: Working directory for the agent
        session_name: Human-readable session name
        status: Session status ("starting", "running", "stopped", "crashed")
        last_input: Last input sent to the agent
        created_at: ISO timestamp of session creation
        last_active_at: ISO timestamp of last activity
        agent: The actual agent instance (set by SessionManager)
    """
    session_id: str
    user_id: str
    template_name: str
    work_dir: str
    session_name: str
    status: str = "starting"
    last_input: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_active_at: str = field(default_factory=lambda: datetime.now().isoformat())
    agent: object = None  # Agent instance, set by SessionManager

    def update_activity(self, input_text: str = None):
        """Update last_active_at timestamp and optionally last_input."""
        self.last_active_at = datetime.now().isoformat()
        if input_text is not None:
            self.last_input = input_text
