# Feishu Multi-Session Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为飞书桥接服务增加按用户隔离的多会话管理、模板驱动 CLI 启动、动态目录路由和新的飞书会话命令。

**Architecture:** 保留现有 `BaseAgent` 进程与输出处理能力，新增模板注册表和会话管理层，再把 `AgentBridgeService` 从单 Agent 控制器改造成基于 `user_id` 和 `session_id` 的路由器。飞书消息解析负责识别模板命令、会话命令和定向消息，服务层统一完成会话生命周期管理。

**Tech Stack:** Python 3, YAML 配置, 现有 PTY/ConPTY 终端封装, pytest, 飞书 Bot 集成

---

### Task 1: Add Template Registry And Config Validation

**Files:**
- Create: `src/agent/template_registry.py`
- Modify: `config/config.yaml.example`
- Test: `tests/agent/test_template_registry.py`

**Step 1: Write the failing test**

```python
from agent.template_registry import TemplateRegistry


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
```

**Step 2: Run test to verify it fails**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\agent\test_template_registry.py -v`

Expected: FAIL with `ModuleNotFoundError` or `TemplateRegistry` not defined.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass


@dataclass
class LaunchSpec:
    command: str
    args: list[str]
    env: dict[str, str]
    append_prompt_as_stdin: bool = True


class TemplateRegistry:
    def __init__(self, templates, allowed_work_roots, max_sessions_per_user):
        self.templates = templates
        self.allowed_work_roots = allowed_work_roots
        self.max_sessions_per_user = max_sessions_per_user

    def build_launch_spec(self, template_name, user_id, session_id, session_name, work_dir):
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

    def _expand(self, value, variables):
        for source, target in variables.items():
            value = value.replace(source, target)
        return value
```

**Step 4: Run test to verify it passes**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\agent\test_template_registry.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /d E:\2026\20260207_01feishu2claudecode
git add tests/agent/test_template_registry.py src/agent/template_registry.py config/config.yaml.example
git commit -m feat-add-template-registry
```

### Task 2: Add Session Persistence And Per-User Session Manager

**Files:**
- Create: `src/session/__init__.py`
- Create: `src/session/manager.py`
- Create: `src/session/models.py`
- Modify: `src/storage/chat_store.py`
- Test: `tests/session/test_session_manager.py`

**Step 1: Write the failing test**

```python
from session.manager import SessionManager


class FakeAgent:
    def __init__(self):
        self.messages = []
        self.running = True

    def start(self):
        return True

    def stop(self):
        self.running = False

    def is_running(self):
        return self.running

    def send_input(self, text):
        self.messages.append(text)


def test_user_sessions_are_isolated():
    manager = SessionManager(
        template_registry=object(),
        agent_factory=lambda spec, callback: FakeAgent(),
        store=None,
    )

    a = manager.create_session("user_a", "codex", r"E:\2026\repo\a", "a1")
    b = manager.create_session("user_b", "codex", r"E:\2026\repo\b", "b1")

    manager.set_active_session("user_a", a.session_id)
    manager.send_to_active_session("user_a", "fix api")

    assert manager.list_sessions("user_b")[0].session_id == b.session_id
    assert manager.get_session("user_b", b.session_id).last_input is None
```

**Step 2: Run test to verify it fails**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\session\test_session_manager.py -v`

Expected: FAIL with `ModuleNotFoundError` or missing `SessionManager`.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentSession:
    session_id: str
    user_id: str
    template_name: str
    work_dir: str
    session_name: str
    status: str = "starting"
    last_input: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class SessionManager:
    def __init__(self, template_registry, agent_factory, store):
        self.template_registry = template_registry
        self.agent_factory = agent_factory
        self.store = store
        self._pools = {}

    def create_session(self, user_id, template_name, work_dir, session_name):
        pool = self._pools.setdefault(user_id, {"sessions": {}, "active_session_id": None})
        session = AgentSession(
            session_id=f"s_{len(pool['sessions']) + 1:03d}",
            user_id=user_id,
            template_name=template_name,
            work_dir=work_dir,
            session_name=session_name,
            status="running",
        )
        session.agent = self.agent_factory(None, None)
        session.agent.start()
        pool["sessions"][session.session_id] = session
        pool["active_session_id"] = session.session_id
        return session
```

**Step 4: Run test to verify it passes**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\session\test_session_manager.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /d E:\2026\20260207_01feishu2claudecode
git add tests/session/test_session_manager.py src/session/__init__.py src/session/models.py src/session/manager.py src/storage/chat_store.py
git commit -m feat-add-session-manager
```

### Task 3: Add Generic Command Agent And Launch Spec Wiring

**Files:**
- Create: `src/agent/command_agent.py`
- Modify: `src/agent/base.py`
- Modify: `src/agent/__init__.py`
- Test: `tests/agent/test_command_agent.py`

**Step 1: Write the failing test**

```python
from agent.command_agent import CommandAgent


def test_command_agent_uses_launch_spec_values():
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
```

**Step 2: Run test to verify it fails**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\agent\test_command_agent.py -v`

Expected: FAIL with `ModuleNotFoundError` or missing `CommandAgent`.

**Step 3: Write minimal implementation**

```python
from agent.base import BaseAgent


class CommandAgent(BaseAgent):
    def __init__(self, config, output_filter_config):
        super().__init__(config, output_filter_config)
        self.extra_env = config.get("env", {})

    def _build_command(self):
        return self.command, self.args
```

并在 `BaseAgent` 中补充对 `env` 的支持，使启动子进程时合并额外环境变量。

**Step 4: Run test to verify it passes**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\agent\test_command_agent.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /d E:\2026\20260207_01feishu2claudecode
git add tests/agent/test_command_agent.py src/agent/command_agent.py src/agent/base.py src/agent/__init__.py
git commit -m feat-add-command-agent
```

### Task 4: Rewrite Feishu Message Parsing For Session Commands

**Files:**
- Modify: `src/feishu/message_handler.py`
- Test: `tests/feishu/test_message_handler.py`

**Step 1: Write the failing test**

```python
from feishu.message_handler import MessageHandler


def test_parse_session_new_command():
    result = MessageHandler.parse_message("/session new codex E:\\repo\\api api-fix")

    assert result["type"] == "system"
    assert result["content"] == "/session new codex E:\\repo\\api api-fix"


def test_parse_directed_session_message():
    result = MessageHandler.parse_message("@sid:s_002 fix the failing tests")

    assert result["type"] == "agent_input"
    assert result["metadata"]["session_id"] == "s_002"
    assert result["content"] == "fix the failing tests"
```

**Step 2: Run test to verify it fails**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\feishu\test_message_handler.py -v`

Expected: FAIL because directed session metadata is not parsed.

**Step 3: Write minimal implementation**

```python
direct_match = re.match(r"^@sid:(?P<session_id>[A-Za-z0-9_-]+)\s+(?P<content>.+)$", text)
if direct_match:
    return {
        "type": "agent_input",
        "content": direct_match.group("content").strip(),
        "metadata": {"session_id": direct_match.group("session_id")},
    }
```

同时更新快捷命令映射，去掉 `/switch`，保留 `/status` 和 `/help`，并增加新的 `/session` 与 `/template` 帮助文案。

**Step 4: Run test to verify it passes**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\feishu\test_message_handler.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /d E:\2026\20260207_01feishu2claudecode
git add tests/feishu/test_message_handler.py src/feishu/message_handler.py
git commit -m feat-add-session-message-routing
```

### Task 5: Replace Single-Agent Service Wiring With Session Routing

**Files:**
- Modify: `src/main.py`
- Modify: `src/monitor/status_monitor.py`
- Modify: `src/feishu/bot.py`
- Test: `tests/service/test_agent_bridge_service.py`

**Step 1: Write the failing test**

```python
from main import AgentBridgeService


def test_plain_message_routes_to_active_session(tmp_path):
    service = AgentBridgeService(config_path=str(tmp_path / "config.yaml"))
    service.session_manager = FakeSessionManager()
    service.feishu_bot = FakeFeishuBot()
    service.monitor = FakeMonitor()

    service._handle_feishu_message("user_a", "fix login bug")

    assert service.session_manager.sent == [("user_a", None, "fix login bug")]
```

**Step 2: Run test to verify it fails**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\service\test_agent_bridge_service.py -v`

Expected: FAIL because the service still expects a single `self.agent`.

**Step 3: Write minimal implementation**

```python
def _handle_feishu_message(self, user_id: str, message: str):
    parsed = MessageHandler.parse_message(message)

    if parsed["type"] == "system":
        self._handle_command(user_id, parsed["content"], source="feishu")
        return

    target_session_id = parsed["metadata"].get("session_id")
    self.session_manager.send_message(
        user_id=user_id,
        content=parsed["content"],
        session_id=target_session_id,
    )
```

并将 `_handle_command` 改造成基于 `SessionManager` 的命令分发器，覆盖：

- `/template list`
- `/template show`
- `/session new`
- `/session list`
- `/session use`
- `/session info`
- `/session stop`
- `/session restart`
- `/session rm`
- `/status`
- `/help`

**Step 4: Run test to verify it passes**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\service\test_agent_bridge_service.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /d E:\2026\20260207_01feishu2claudecode
git add tests/service/test_agent_bridge_service.py src/main.py src/monitor/status_monitor.py src/feishu/bot.py
git commit -m feat-route-feishu-through-sessions
```

### Task 6: Persist Session Metadata And Update User-Facing Docs

**Files:**
- Modify: `src/storage/chat_store.py`
- Modify: `README.md`
- Modify: `config/config.yaml.example`
- Test: `tests/session/test_session_persistence.py`

**Step 1: Write the failing test**

```python
from storage.chat_store import ChatStore


def test_session_records_are_persisted(tmp_path):
    store = ChatStore(storage_dir=str(tmp_path))
    store.save_session_record(
        {
            "session_id": "s_001",
            "user_id": "ou_123",
            "template_name": "codex",
            "work_dir": r"E:\2026\repo\api",
            "status": "stopped",
        }
    )

    records = store.load_session_records()

    assert records[0]["session_id"] == "s_001"
    assert records[0]["template_name"] == "codex"
```

**Step 2: Run test to verify it fails**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\session\test_session_persistence.py -v`

Expected: FAIL because session persistence methods do not exist.

**Step 3: Write minimal implementation**

```python
def save_session_record(self, record: dict):
    path = os.path.join(self.storage_dir, "sessions.json")
    records = self.load_session_records()
    existing = [item for item in records if item["session_id"] != record["session_id"]]
    existing.append(record)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def load_session_records(self):
    path = os.path.join(self.storage_dir, "sessions.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
```

同时更新 `README.md` 与配置示例，补充多会话和模板命令说明。

**Step 4: Run test to verify it passes**

Run: `cd /d E:\2026\20260207_01feishu2claudecode && pytest tests\session\test_session_persistence.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /d E:\2026\20260207_01feishu2claudecode
git add tests/session/test_session_persistence.py src/storage/chat_store.py README.md config/config.yaml.example
git commit -m feat-persist-session-records
```

### Task 7: Run Verification And Manual Smoke Checks

**Files:**
- Modify: `README.md`

**Step 1: Run focused automated tests**

Run:

```bash
cd /d E:\2026\20260207_01feishu2claudecode
pytest tests\agent\test_template_registry.py tests\agent\test_command_agent.py tests\session\test_session_manager.py tests\session\test_session_persistence.py tests\feishu\test_message_handler.py tests\service\test_agent_bridge_service.py -v
```

Expected: PASS

**Step 2: Run full test suite**

Run:

```bash
cd /d E:\2026\20260207_01feishu2claudecode
pytest -v
```

Expected: PASS, or if legacy tests fail, record exact failures and isolate them from the new feature branch before proceeding.

**Step 3: Manual smoke test**

Run:

```bash
cd /d E:\2026\20260207_01feishu2claudecode
python src\main.py
```

Manual checks:

- 发送 `/template list`
- 发送 `/session new codex E:\2026\some_repo demo`
- 发送普通文本，确认命中活动会话
- 发送 `@sid:s_001 status`
- 发送 `/session list`
- 发送 `/session stop s_001`
- 重启服务，确认会话记录仍可查看且状态为 `stopped`

**Step 4: Update README validation notes**

补充已验证命令、目录白名单限制和服务重启后的行为说明。

**Step 5: Commit**

```bash
cd /d E:\2026\20260207_01feishu2claudecode
git add README.md
git commit -m docs-add-session-smoke-test-notes
```
