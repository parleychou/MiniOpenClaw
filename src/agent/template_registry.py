# src/agent/template_registry.py
"""
Template Registry for Agent CLI templates.
Provides template-based agent instantiation with variable expansion.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class LaunchSpec:
    """Specification for launching an agent process."""
    command: str
    args: List[str]
    env: Dict[str, str]
    append_prompt_as_stdin: bool = True


class TemplateRegistry:
    """
    Registry for CLI agent templates.
    Templates define how to launch different CLI agents with variable substitution.
    """

    def __init__(self, templates: dict, allowed_work_roots: List[str], max_sessions_per_user: int):
        """
        Initialize the template registry.

        Args:
            templates: Dictionary of template definitions keyed by template name
            allowed_work_roots: List of allowed working directory roots for security
            max_sessions_per_user: Maximum sessions allowed per user
        """
        self.templates = templates
        self.allowed_work_roots = allowed_work_roots
        self.max_sessions_per_user = max_sessions_per_user

    def get_template(self, template_name: str) -> Optional[dict]:
        """Get a template by name."""
        return self.templates.get(template_name)

    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self.templates.keys())

    def validate_work_dir(self, work_dir: str) -> bool:
        """
        Validate that a work directory is within allowed roots.

        Args:
            work_dir: The work directory path to validate

        Returns:
            True if valid, False otherwise
        """
        import os
        work_dir = os.path.abspath(work_dir)
        for root in self.allowed_work_roots:
            root = os.path.abspath(root)
            if work_dir.startswith(root):
                return True
        return False

    def build_launch_spec(
        self,
        template_name: str,
        user_id: str,
        session_id: str,
        session_name: str,
        work_dir: str,
    ) -> LaunchSpec:
        """
        Build a LaunchSpec from a template with variable expansion.

        Args:
            template_name: Name of the template to use
            user_id: User ID for ${user_id} substitution
            session_id: Session ID for ${session_id} substitution
            session_name: Session name for ${session_name} substitution
            work_dir: Working directory for ${work_dir} substitution

        Returns:
            LaunchSpec with expanded variables

        Raises:
            KeyError: If template_name is not found
        """
        template = self.templates[template_name]

        variables = {
            "${work_dir}": work_dir,
            "${session_id}": session_id,
            "${user_id}": user_id,
            "${session_name}": session_name,
        }

        args = [self._expand(value, variables) for value in template.get("args", [])]
        env = {
            key: self._expand(value, variables)
            for key, value in template.get("env", {}).items()
        }

        return LaunchSpec(
            command=template["command"],
            args=args,
            env=env,
            append_prompt_as_stdin=template.get("append_prompt_as_stdin", True),
        )

    def _expand(self, value: str, variables: dict) -> str:
        """
        Expand variables in a string value.

        Args:
            value: String with ${variable} placeholders
            variables: Dictionary mapping variable names to values

        Returns:
            Expanded string
        """
        for source, target in variables.items():
            value = value.replace(source, target)
        return value
