# src/session/manager.py
"""Session manager for per-user session pools."""

from typing import Dict, List, Optional, Callable, Any
from .models import AgentSession


class SessionManager:
    """
    Manages per-user session pools for multi-session agent support.

    Each user has their own session pool with:
    - Multiple concurrent sessions
    - One active session for routing plain messages

    Architecture:
        user_id -> UserSessionPool -> sessions[session_id] -> AgentSession
    """

    def __init__(self, template_registry, agent_factory: Callable, store=None):
        """
        Initialize SessionManager.

        Args:
            template_registry: TemplateRegistry instance for building launch specs
            agent_factory: Callable that creates agent instances
                Signature: (config, output_filter_config) -> Agent
            store: Optional storage backend for persistence
        """
        self.template_registry = template_registry
        self.agent_factory = agent_factory
        self.store = store
        # user_id -> {"sessions": {session_id: AgentSession}, "active_session_id": str}
        self._pools: Dict[str, dict] = {}

    def create_session(
        self,
        user_id: str,
        template_name: str,
        work_dir: str,
        session_name: str,
    ) -> AgentSession:
        """
        Create a new session for a user.

        Args:
            user_id: Feishu user ID
            template_name: Name of template to use
            work_dir: Working directory
            session_name: Human-readable session name

        Returns:
            The created AgentSession instance
        """
        pool = self._pools.setdefault(user_id, {"sessions": {}, "active_session_id": None})

        # Generate session ID
        session_count = len(pool["sessions"])
        session_id = f"s_{session_count + 1:03d}"

        # Create session
        session = AgentSession(
            session_id=session_id,
            user_id=user_id,
            template_name=template_name,
            work_dir=work_dir,
            session_name=session_name,
            status="running",
        )

        # Create and start agent using factory
        # Pass None for config since we're using template-based creation
        session.agent = self.agent_factory(None, None)
        if hasattr(session.agent, 'start'):
            session.agent.start()

        # Store session
        pool["sessions"][session_id] = session
        pool["active_session_id"] = session_id

        return session

    def get_session(self, user_id: str, session_id: str) -> Optional[AgentSession]:
        """
        Get a specific session by ID.

        Args:
            user_id: Feishu user ID
            session_id: Session ID

        Returns:
            AgentSession if found, None otherwise
        """
        pool = self._pools.get(user_id)
        if not pool:
            return None
        return pool["sessions"].get(session_id)

    def get_active_session(self, user_id: str) -> Optional[AgentSession]:
        """
        Get the active session for a user.

        Args:
            user_id: Feishu user ID

        Returns:
            Active AgentSession if exists, None otherwise
        """
        pool = self._pools.get(user_id)
        if not pool or not pool["active_session_id"]:
            return None
        return pool["sessions"].get(pool["active_session_id"])

    def set_active_session(self, user_id: str, session_id: str) -> bool:
        """
        Set the active session for a user.

        Args:
            user_id: Feishu user ID
            session_id: Session ID to make active

        Returns:
            True if successful, False if session not found
        """
        pool = self._pools.get(user_id)
        if not pool or session_id not in pool["sessions"]:
            return False
        pool["active_session_id"] = session_id
        return True

    def list_sessions(self, user_id: str) -> List[AgentSession]:
        """
        List all sessions for a user.

        Args:
            user_id: Feishu user ID

        Returns:
            List of AgentSession instances
        """
        pool = self._pools.get(user_id)
        if not pool:
            return []
        return list(pool["sessions"].values())

    def send_to_active_session(self, user_id: str, content: str) -> bool:
        """
        Send a message to the user's active session.

        Args:
            user_id: Feishu user ID
            content: Message content

        Returns:
            True if message was sent, False if no active session
        """
        session = self.get_active_session(user_id)
        if not session:
            return False

        session.update_activity(content)

        if session.agent and hasattr(session.agent, 'send_input'):
            session.agent.send_input(content)
        return True

    def send_to_session(
        self,
        user_id: str,
        session_id: str,
        content: str,
    ) -> bool:
        """
        Send a message to a specific session.

        Args:
            user_id: Feishu user ID
            session_id: Target session ID
            content: Message content

        Returns:
            True if message was sent, False if session not found
        """
        session = self.get_session(user_id, session_id)
        if not session:
            return False

        session.update_activity(content)

        if session.agent and hasattr(session.agent, 'send_input'):
            session.agent.send_input(content)
        return True

    def stop_session(self, user_id: str, session_id: str) -> bool:
        """
        Stop a session's agent.

        Args:
            user_id: Feishu user ID
            session_id: Session ID

        Returns:
            True if stopped, False if not found
        """
        session = self.get_session(user_id, session_id)
        if not session:
            return False

        session.status = "stopped"
        if session.agent and hasattr(session.agent, 'stop'):
            session.agent.stop()
        return True

    def restart_session(self, user_id: str, session_id: str) -> bool:
        """
        Restart a session's agent.

        Args:
            user_id: Feishu user ID
            session_id: Session ID

        Returns:
            True if restarted, False if not found
        """
        session = self.get_session(user_id, session_id)
        if not session:
            return False

        # Stop existing agent
        if session.agent and hasattr(session.agent, 'stop'):
            session.agent.stop()

        # Create new agent
        session.agent = self.agent_factory(None, None)
        if hasattr(session.agent, 'start'):
            session.agent.start()

        session.status = "running"
        return True

    def remove_session(self, user_id: str, session_id: str) -> bool:
        """
        Remove a session.

        Args:
            user_id: Feishu user ID
            session_id: Session ID

        Returns:
            True if removed, False if not found
        """
        pool = self._pools.get(user_id)
        if not pool or session_id not in pool["sessions"]:
            return False

        session = pool["sessions"][session_id]

        # Stop agent if running
        if session.agent and hasattr(session.agent, 'stop'):
            session.agent.stop()

        # Remove from pool
        del pool["sessions"][session_id]

        # Clear active session if it was this one
        if pool["active_session_id"] == session_id:
            # Set to most recent remaining session or None
            pool["active_session_id"] = (
                list(pool["sessions"].keys())[-1] if pool["sessions"] else None
            )

        return True

    def get_pool_info(self, user_id: str) -> dict:
        """
        Get information about a user's session pool.

        Args:
            user_id: Feishu user ID

        Returns:
            Dict with session count, active session ID, etc.
        """
        pool = self._pools.get(user_id)
        if not pool:
            return {"session_count": 0, "active_session_id": None}

        return {
            "session_count": len(pool["sessions"]),
            "active_session_id": pool["active_session_id"],
            "sessions": [
                {
                    "session_id": s.session_id,
                    "session_name": s.session_name,
                    "template_name": s.template_name,
                    "status": s.status,
                }
                for s in pool["sessions"].values()
            ],
        }
