import pytest
from agent.template_registry import TemplateRegistry, LaunchSpec


def test_expand_template_with_runtime_variables():
    registry = TemplateRegistry(
        templates={
            "codex": {
                "command": "codex",
                "args": ["--cwd", "${work_dir}", "--session", "${session_id}"],
                "env": {"FEISHU_USER": "${user_id}"},
            }
        },
        allowed_work_roots=[r"E:\2026"],
        max_sessions_per_user=5,
    )

    result = registry.build_launch_spec(
        "codex",
        user_id="ou_123",
        session_id="s_001",
        session_name="api-fix",
        work_dir=r"E:\2026\repo\api",
    )

    assert result.command == "codex"
    assert result.args == ["--cwd", r"E:\2026\repo\api", "--session", "s_001"]
    assert result.env["FEISHU_USER"] == "ou_123"


def test_launch_spec_dataclass_fields():
    spec = LaunchSpec(
        command="test",
        args=["arg1"],
        env={"KEY": "value"},
        append_prompt_as_stdin=True,
    )
    assert spec.command == "test"
    assert spec.args == ["arg1"]
    assert spec.env == {"KEY": "value"}
    assert spec.append_prompt_as_stdin is True


def test_expand_all_variables():
    registry = TemplateRegistry(
        templates={
            "test": {
                "command": "cmd",
                "args": ["${session_name}", "${work_dir}"],
                "env": {"SID": "${session_id}"},
            }
        },
        allowed_work_roots=[],
        max_sessions_per_user=3,
    )

    result = registry.build_launch_spec(
        "test",
        user_id="user1",
        session_id="s_99",
        session_name="my-session",
        work_dir=r"E:\work",
    )

    assert result.args == ["my-session", r"E:\work"]
    assert result.env["SID"] == "s_99"
