# Feishu Agent Bridge - Implementation Documentation

## 1. Project Overview

**Feishu Agent Bridge** is a service that connects Feishu (Lark) bots with AI coding assistants (Claude Code/OpenCode), enabling remote control of AI programming tools through Feishu messaging.

### 1.1 Core Features

- **Feishu Bot Integration** - Interact with AI agents through Feishu messages
- **Intelligent Output Filtering** - Forward only critical information (confirmations, errors, results)
- **Bidirectional Real-time Communication** - Support for command sending and result receiving
- **Status Monitoring** - Timeout alerts, heartbeat detection
- **Multi-Agent Support** - Compatible with Claude Code and OpenCode
- **Web Dashboard** - Real-time chat history and statistics
- **Chat History Storage** - Automatic conversation logging (JSONL format)
- **Dual Connection Modes** - WebSocket (long connection) or Webhook callback

### 1.2 Architecture Overview

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────┐
│   Feishu    │◄───────►│  Agent Bridge    │◄───────►│ Claude Code │
│   (Lark)    │         │   (This Service) │         │  /OpenCode  │
└─────────────┘         └──────────────────┘         └─────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │ Web Dashboard │
                        └──────────────┘
```

---

## 2. Project Structure

```
feishu-agent-bridge/
├── config/
│   └── config.yaml              # Configuration (not committed)
├── src/
│   ├── main.py                  # Main entry point (AgentBridgeService)
│   ├── main_simple.py           # Simplified entry point (SimpleBridgeService)
│   ├── feishu/                  # Feishu bot module
│   │   ├── bot.py               # FeishuBot - HTTP server, message handling
│   │   ├── lark_client.py       # LarkEventClient - Official SDK WebSocket
│   │   ├── websocket_client.py  # Custom WebSocket implementation
│   │   └── message_handler.py    # Message parsing and formatting
│   ├── agent/                   # Agent adapters
│   │   ├── base.py              # BaseAgent abstract class
│   │   ├── claude_code.py       # ClaudeCodeAgent adapter
│   │   ├── opencode.py          # OpenCodeAgent adapter
│   │   ├── output_filter.py     # OutputFilter - intelligent filtering
│   │   ├── simple_agent.py      # SimpleAgent (simplified)
│   │   └── simple_filter.py     # SimpleFilter (simplified)
│   ├── terminal/                # Terminal/PTY management
│   │   ├── pty_manager.py       # PTYManager, WinPTYManager
│   │   ├── conpty_manager.py    # ConPTYManager (Windows 10+)
│   │   └── simple_pty.py        # SimplePTY (simplified)
│   ├── monitor/                 # Monitoring module
│   │   └── status_monitor.py    # StatusMonitor - health checks
│   ├── storage/                 # Storage module
│   │   └── chat_store.py        # ChatStore - JSONL persistence
│   └── utils/                   # Utility module
│       ├── logger.py            # Colored console logger
│       └── tunnel.py            # NgrokTunnel for expose
├── web/
│   └── dashboard.html           # Web dashboard (38KB)
├── data/                        # Chat history (JSONL files)
├── logs/                        # Log files
├── tests/                       # Test directory (empty)
├── requirements.txt             # Python dependencies
└── start.bat/start.sh           # Startup scripts
```

---

## 3. Module Details

### 3.1 Main Entry Point (`src/main.py`)

**Class: `AgentBridgeService`**

The main controller managing the entire service lifecycle.

**Key Responsibilities:**
- Load and validate configuration
- Initialize Agent (Claude Code or OpenCode)
- Initialize StatusMonitor
- Initialize FeishuBot
- Handle system commands (`/status`, `/switch`, `/restart`, `/stop`, `/help`)
- Console input loop
- Graceful shutdown with signal handling

**Key Methods:**
```python
def start(self):
    """Start the service - initialization order:
    1. Init Agent (not started yet)
    2. Init StatusMonitor and start it
    3. Init FeishuBot
    4. Set alert callback for StatusMonitor
    5. Set Feishu callback for Agent
    6. Start Agent process
    7. Start Feishu event listener (HTTP server)
    8. Notify via Feishu that service started
    9. Enter console input loop
    """

def _handle_feishu_message(self, user_id: str, message: str):
    """Process incoming Feishu messages
    - System commands (starting with '/')
    - User messages -> Agent
    """

def _handle_command(self, command: str, source: str):
    """Handle system commands from console or Feishu"""

def _switch_agent(self, agent_type: str):
    """Switch between Claude Code and OpenCode"""

def _restart_agent(self):
    """Restart the current agent"""

def stop(self):
    """Graceful shutdown - send notification, stop monitor, stop agent"""
```

### 3.2 Feishu Bot (`src/feishu/bot.py`)

**Class: `FeishuBot`**

Handles all Feishu-related communication and provides HTTP endpoints.

**Connection Modes:**
1. **WebSocket (Recommended)** - Uses official Lark SDK for persistent connection
2. **Webhook** - HTTP callbacks from Feishu (requires public URL)

**Key Attributes:**
```python
self.app_id: str
self.app_secret: str
self.verification_token: str
self.encrypt_key: str
self.connection_mode: str  # "websocket" or "webhook"
self.allowed_users: set    # OpenIDs allowed to use the bot
self.chat_store: ChatStore # Message persistence
self.lark_client: LarkEventClient  # WebSocket client
```

**HTTP Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/feishu/event` | POST | Handle Feishu event callbacks |
| `/health` | GET | Health check with agent status |
| `/` | GET | Web dashboard |
| `/api/chat/messages` | POST | Get chat history (supports filtering) |
| `/api/chat/clear` | POST | Clear chat history |
| `/api/chat/send` | POST | Send message from web to agent |
| `/test/feishu` | POST | Test endpoint for Feishu events |

**Key Methods:**
```python
def _handle_event_v2(self, data: dict):
    """Handle v2 event format from Feishu
    - Message deduplication (event_id tracking)
    - Sender type checking (ignore bot's own messages)
    - User permission checking
    """

def _handle_lark_message(self, sender_id: str, text: str, chat_id: str):
    """Handle messages from Lark SDK WebSocket"""

def _on_agent_output(self, message: str, msg_type: str):
    """Callback for Agent output
    - Save to chat_store
    - Send to Feishu if chat_id available
    """

def send_text(self, text: str, chat_id: str = None):
    """Send text message
    - If webhook_url configured: use webhook
    - Otherwise: use Feishu API to send to chat_id
    - Fallback: search chat history for chat_id
    """

def _send_via_api(self, text: str, chat_id: str):
    """Send via Feishu Open API
    - Get tenant_access_token
    - POST to /im/v1/messages
    """
```

**Message Flow:**
1. Feishu sends event (WebSocket or Webhook)
2. `handle_event` or `_handle_lark_message` processes it
3. Permission check against `allowed_users`
4. Save to `chat_store`
5. Call `on_message` callback (which routes to Agent)
6. Agent output -> `_on_agent_output` -> `send_text` -> Feishu

### 3.3 Agent Module (`src/agent/`)

#### 3.3.1 Base Agent (`src/agent/base.py`)

**Class: `BaseAgent`** (Abstract)

Base class for all agent adapters.

**Key Attributes:**
```python
self.config: dict
self.command: str          # Agent executable path
self.args: list            # Command arguments
self.work_dir: str         # Working directory
self._pty: PTYManager      # Terminal manager
self._output_filter: OutputFilter
self._feishu_callback: Callable
self._status: str          # "initialized", "running", "stopped"
self._start_time: float
self._command_count: int
```

**Key Methods:**
```python
def start(self) -> bool:
    """Start the agent process
    - Windows: Use WinPTYManager for real PTY
    - Unix: Use PTYManager
    - Auto-accept Claude Code confirmation (Down + Enter)
    """

def send_input(self, text: str):
    """Send input to agent process"""

def is_running(self) -> bool:
    """Check if agent process is running"""

def get_status(self) -> dict:
    """Get agent status including:
    - status, agent_type, command, work_dir
    - uptime, command_count
    - filter_state, idle_time
    """

def set_feishu_callback(self, callback: Callable):
    """Set callback for filtered output to be sent to Feishu"""
```

#### 3.3.2 Claude Code Agent (`src/agent/claude_code.py`)

**Class: `ClaudeCodeAgent`** (extends BaseAgent)

Claude Code specific adapter.

**Features:**
- Auto-accepts terms of service on first run
- Uses `WinPTYManager` for PTY support
- Confirmation patterns for user prompts

#### 3.3.3 OpenCode Agent (`src/agent/opencode.py`)

**Class: `OpenCodeAgent`** (extends BaseAgent)

OpenCode specific adapter.

#### 3.3.4 Output Filter (`src/agent/output_filter.py`)

**Class: `OutputFilter`**

Intelligent output filtering to reduce noise in Feishu messages.

**Filtering Strategy:**

1. **Ignore Patterns** (configured in `config.yaml`):
   - Thinking processes
   - Loading animations
   - Debug information
   - Empty lines and separators

2. **Forward Patterns** (configured in `config.yaml`):
   - Confirmation requests (`y/n`, `Do you want...`)
   - Error messages
   - Execution results
   - Progress information

3. **Deduplication**:
   - Line-level dedup with 5-second window
   - Message-level dedup with similarity check (Levenshtein distance)
   - 50% similarity threshold

4. **Message Types:**
   - `confirm` - Immediate forwarding (user needs to respond)
   - `error` - Immediate forwarding (urgent)
   - `result` - Buffered (aggregated output)
   - `progress` - Throttled (latest only)
   - `info` - Normal buffered output

**Key Methods:**
```python
def process_line(self, line: str):
    """Process single line of agent output
    1. Clean ANSI codes and control characters
    2. Check ignore patterns
    3. Skip thinking/loading detection
    4. Deduplicate
    5. Classify message type
    6. Forward immediately (confirm/error) or buffer (result/info)
    """

def _classify_line(self, line: str) -> str:
    """Classify using regex patterns:
    - confirm_patterns: y/n, Do you want, Press Enter, etc.
    - error_patterns: Error, Exception, Permission denied, etc.
    - result_patterns: Done, Created, files changed, etc.
    - progress_patterns: \d+/\d+, Installing, etc.
    """

def _flush_buffer(self, msg_type: str):
    """Flush buffered lines
    1. Clean all lines
    2. Deduplicate using stable key
    3. If >80% similar, keep only last 3
    4. Progress: keep only last line
    5. Combine and forward
    """
```

### 3.4 Terminal Module (`src/terminal/`)

#### 3.4.1 PTY Manager (`src/terminal/pty_manager.py`)

**Classes:**
- `PTYManager` - Base PTY manager using subprocess
- `WinPTYManager` - Enhanced PTY using winpty library

**PTYManager Key Methods:**
```python
def start(self) -> bool:
    """Start process
    - Try WinPTY first (Windows)
    - Fallback to subprocess
    """

def send_input(self, text: str):
    """Send input to process stdin"""

def _read_output(self):
    """Thread: read stdout, clean ANSI, call callback"""

def _read_stderr(self):
    """Thread: read stderr"""

def _strip_ansi(self, text: str) -> str:
    """Remove ANSI escape sequences and control characters"""

def is_running(self) -> bool:
    """Check if process is alive"""

def stop(self):
    """Graceful shutdown: try /exit, exit, then terminate"""
```

**WinPTYManager Enhancements:**
```python
def _read_pty_output(self):
    """Smart line accumulation for loading animations
    - Buffer until \n or stable threshold (500ms)
    - Detect loading animations
    - Handle line overwrites (\r without \n)
    """

def _is_loading_animation(self, text: str) -> bool:
    """Detect loading animations:
    - Repeated characters (e.g., 'zzz', '...')
    - Loading keywords (razzmatazz, thinking, etc.)
    - Few unique characters (<=5)
    """

def send_input(self, text: str):
    """Send with UTF-8 encoding, handle single digit input"""
```

### 3.5 Monitor Module (`src/monitor/status_monitor.py`)

**Class: `StatusMonitor`**

Monitors agent health and sends alerts.

**Key Attributes:**
```python
self.check_interval: int         # Status check interval (default: 5s)
self.timeout_threshold: int     # Command timeout (default: 300s)
self.heartbeat_interval: int    # Heartbeat interval (default: 60s)
self._last_command_time: float
self._current_command: str
self._command_history: list     # Last 100 commands
self._alerts: list
self._feishu_alert_callback: Callable
```

**Key Methods:**
```python
def record_command(self, command: str):
    """Record command execution start time"""

def _monitor_loop(self):
    """Main monitoring loop
    - Check if agent process is running
    - Check command timeout
    - Send heartbeat
    """

def _alert(self, message: str):
    """Send alert via callback and store"""

def get_status_report(self) -> str:
    """Generate formatted status report:
    - Agent type, status, directory
    - Uptime (formatted as h:m:s)
    - Command count, filter state, idle time
    - Recent commands
    - Recent alerts (last 5 minutes)
    """
```

### 3.6 Storage Module (`src/storage/chat_store.py`)

**Class: `ChatStore`**

JSONL-based chat history storage.

**Key Attributes:**
```python
self.max_messages: int       # Max in-memory (default: 1000)
self._messages: deque        # In-memory message buffer
self.storage_dir: str        # Data directory
self.log_file: str           # Today's log file (chat_YYYYMMDD.jsonl)
```

**Message Schema:**
```json
{
  "id": "msg_1234567890_42",
  "timestamp": "2026-03-19T10:30:00.123456",
  "role": "user|assistant|system",
  "content": "message text",
  "type": "text|confirm|error|result|progress",
  "metadata": {
    "sender_id": "ou_xxx",
    "chat_id": "oc_xxx",
    "source": "feishu|web"
  }
}
```

**Key Methods:**
```python
def add_message(self, role: str, content: str, msg_type: str, metadata: dict):
    """Add message to memory and persist to JSONL"""

def get_messages(self, limit: int, offset: int) -> List[dict]:
    """Get messages (newest first)"""

def get_stats(self) -> dict:
    """Get statistics:
    - total count
    - by_role (user/assistant/system)
    - by_type (text/confirm/error/result/progress)
    - first/last message timestamp
    """

def clear(self):
    """Clear in-memory messages (file not deleted)"""
```

---

## 4. Configuration (`config/config.yaml`)

```yaml
feishu:
  app_id: "cli_xxx"                    # Feishu App ID
  app_secret: "xxx"                     # Feishu App Secret
  verification_token: "xxx"            # Webhook verification token
  encrypt_key: "xxx"                   # Webhook encryption key
  webhook_url: ""                       # Webhook URL (optional)
  server_port: 9980                     # HTTP server port
  connection_mode: "websocket"          # "websocket" or "webhook"
  allowed_users: []                     # Allowed OpenIDs (empty = all)

agent:
  default: "claude_code"               # Default agent type
  claude_code:
    command: "C:/Users/.../claude.cmd" # Claude Code path
    work_dir: "E:/2026/..."            # Working directory
    args: ["--dangerously-skip-permissions"]
  opencode:
    command: "C:/Users/.../opencode.cmd"
    work_dir: "E:/2026/..."
    args: []

monitor:
  check_interval: 5                    # Status check interval (seconds)
  timeout_threshold: 300                # Command timeout (seconds)
  heartbeat_interval: 60                # Heartbeat interval (seconds)

output_filter:
  forward_patterns:                    # Patterns that trigger forwarding
    - "Error"
    - "Confirm"
    - "Do you want"
  ignore_patterns:                     # Patterns to ignore (100+ patterns)
    - "razzmatazz"
    - "thinking"
    - "Loading"
    - "..."
  max_message_length: 2000             # Max message size
  dedup_enabled: true                  # Enable deduplication
  dedup_similarity_threshold: 0.50     # Similarity threshold (50%)
  line_dedup_time_window: 5            # Line dedup window (seconds)
```

---

## 5. Data Flow

### 5.1 User Sends Message via Feishu

```
1. Feishu Platform
   └── Event (WebSocket or Webhook)
       └── /feishu/event endpoint

2. FeishuBot._handle_event_v2()
   ├── Validate event_id (dedup)
   ├── Check sender_type (ignore bot)
   ├── Check allowed_users
   ├── Parse message content
   └── Store in chat_store

3. FeishuBot._process_message_event()
   └── Call on_message callback

4. AgentBridgeService._handle_feishu_message()
   ├── Check if system command (starts with '/')
   ├── Record command in StatusMonitor
   └── Agent.send_input()

5. Agent (Claude Code / OpenCode)
   └── PTY receives input
       └── Process executes

6. Agent outputs via PTY
   └── PTYManager._read_output()

7. BaseAgent._on_raw_output()
   └── OutputFilter.process_line()

8. OutputFilter
   ├── Clean ANSI codes
   ├── Check ignore patterns
   ├── Deduplicate
   ├── Classify message type
   └── Forward (immediate or buffered)

9. FeishuBot._on_agent_output()
   ├── Store in chat_store
   └── send_text() -> Feishu API

10. User receives message in Feishu
```

### 5.2 Service Startup Sequence

```
AgentBridgeService.start()
│
├── 1. Print banner and config info
│
├── 2. _init_agent(start_agent=False)
│   ├── Create ClaudeCodeAgent or OpenCodeAgent
│   └── Initialize OutputFilter
│
├── 3. StatusMonitor(config, agent).start()
│   └── Start _monitor_loop thread
│
├── 4. FeishuBot(config, agent, monitor, on_message)
│   ├── Setup Flask routes
│   ├── Init ChatStore
│   └── If WebSocket mode: create LarkEventClient
│
├── 5. monitor.set_alert_callback(feishu_bot.send_text)
│
├── 6. agent.set_feishu_callback(feishu_bot._on_agent_output)
│
├── 7. agent.start()
│   ├── PTYManager.start()
│   ├── Start subprocess or WinPTY
│   └── Auto-accept Claude Code confirmation
│
├── 8. feishu_bot.start()
│   ├── If WebSocket: LarkEventClient.start() in thread
│   └── Flask app.run() (blocks)
│
└── 9. feishu_bot.send_text("Service started")
```

---

## 6. Web Dashboard API

### 6.1 Endpoints

**GET `/`**
- Returns `dashboard.html`

**POST `/api/chat/messages`**
```json
Request:
{
  "role": "all|user|assistant",  // Filter by role
  "type": "all|text|confirm|...", // Filter by type
  "limit": 100                    // Max messages
}

Response:
{
  "messages": [...],
  "stats": {
    "total": 42,
    "by_role": {"user": 20, "assistant": 22},
    "by_type": {"text": 40, "confirm": 2},
    "first_message": "2026-03-19T10:00:00",
    "last_message": "2026-03-19T12:00:00"
  }
}
```

**POST `/api/chat/clear`**
```json
Response: {"success": true}
```

**POST `/api/chat/send`**
```json
Request:
{
  "message": "Hello from web"
}

Response:
{
  "success": true,
  "message": "Message sent"
}
```

**GET `/health`**
```json
Response:
{
  "status": "ok",
  "agent": {
    "status": "running",
    "agent_type": "ClaudeCodeAgent",
    "command": "claude.cmd",
    "work_dir": "E:/2026/...",
    "uptime": 3600.5,
    "command_count": 15
  }
}
```

---

## 7. System Commands

| Command | Source | Description |
|---------|--------|-------------|
| `/status` | Both | Show agent status, uptime, recent commands |
| `/switch` | Both | Toggle between Claude Code and OpenCode |
| `/restart` | Both | Restart current agent |
| `/stop` | Both | Stop the service |
| `/help` | Both | Show help information |

---

## 8. Key Implementation Details

### 8.1 ANSI Code Cleaning

Both `PTYManager._strip_ansi()` and `OutputFilter._clean_ansi_codes()` clean:
- Color codes (`\x1b[...m`)
- CSI sequences (`\x1b[...a-zA-Z`)
- OSC sequences (`\x1b]...\x07`)
- Box Drawing characters (`\u2500-\u257F`)
- Geometric Shapes (`\u25A0-\u25FF`)
- Loading animation characters
- Control characters (except \n, \r, \t)

### 8.2 Message Deduplication

Two-level deduplication:

1. **Line-level (fast)**
   - Normalize: lowercase, remove spaces, non-alphanumeric
   - Check `_recent_lines_cache` (deque, maxlen=50)
   - Check `_recent_line_times` dict (5-second window)

2. **Message-level (thorough)**
   - Levenshtein distance-based similarity
   - 50% similarity threshold
   - 60-second time window
   - If >80% of buffered lines are identical, keep only last 3

### 8.3 Loading Animation Detection

Detected by `WinPTYManager._is_loading_animation()`:
- Repeated characters: `(.)\1{2,}` (e.g., "zzz", "...")
- Keywords: "razzmatazz", "thinking", "concocting", etc.
- Few unique chars: `unique_chars <= 5 and len > 10`

### 8.4 PTY Selection Logic

```python
if sys.platform == 'win32':
    pty_manager = WinPTYManager  # Preferred (real PTY)
else:
    pty_manager = PTYManager     # Unix pseudoterminal

# WinPTYManager fallback chain:
# 1. Try winpty library
# 2. Fallback to subprocess
```

### 8.5 Claude Code Auto-Confirmation

On first run, Claude Code shows terms of service. The service automatically:
1. Sends Down arrow key (`\x1b[B`) to select "Yes, I accept"
2. Sends Enter key (`\r`)
3. Waits 3 seconds for initialization

---

## 9. File Storage

### 9.1 Chat History (`data/chat_YYYYMMDD.jsonl`)

Each line is a JSON object:
```
{"id":"msg_123_1","timestamp":"2026-03-19T10:00:00","role":"user","content":"Hello","type":"text","metadata":{...}}
{"id":"msg_123_2","timestamp":"2026-03-19T10:00:01","role":"assistant","content":"Hi","type":"text","metadata":{...}}
```

### 9.2 Logs (`logs/`)

Log files follow naming convention: `agent_bridge_YYYYMMDD.log`

---

## 10. Security Considerations

1. **allowed_users** - Restrict access by OpenID
2. **config.yaml not committed** - Contains secrets
3. **No hardcoded credentials** - All from config file
4. **Token management** - Automatic refresh of tenant_access_token
5. **Message deduplication** - Prevents replay attacks

---

## 11. Dependencies

```
flask>=2.0
requests>=2.25
pyyaml>=5.4
pywinpty>=1.1.0      # Windows PTY support
websockets>=10.0     # WebSocket client
lark-oapi>=1.0.0     # Feishu SDK (optional, for WebSocket mode)
colorama>=0.4        # Colored console output
```

---

## 12. Entry Points

### 12.1 Production
```bash
# Windows
start.bat

# Linux/Mac
./start.sh
```

### 12.2 Development
```bash
python src/main.py
# or
python src/main_simple.py
```

### 12.3 Custom Config
```bash
python src/main.py /path/to/config.yaml
```

---

## Appendix A: Utils Module (`src/utils/`)

### A.1 Logger (`src/utils/logger.py`)

**Class: `Logger`**

Colored console logging with file output.

**Features:**
- **Colored Output**: DEBUG (cyan), INFO (green), WARNING (yellow), ERROR (red)
- **File Logging**: Daily rotating log files (`logs/agent_bridge_YYYYMMDD.log`)
- **UTF-8 Support**: Handles Chinese and special characters
- **Safe Encoding**: Falls back to ASCII on encoding errors

**Usage:**
```python
from utils.logger import Logger

logger = Logger("module_name")
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

---

## Appendix B: Multi-Session Agent Design (Planned)

The project has a design document for a future multi-session architecture (`docs/plans/2026-03-12-feishu-multi-session-agent-design.md`).

### Current State (Single Session)
- One Feishu bot maps to one fixed-directory Agent process
- Single `work_dir` from configuration
- No per-user session isolation
- No support for dynamic directory switching

### Future State (Multi-Session)
- **Session Model**: `user_id -> UserSessionPool -> sessions[] -> AgentSession`
- **Template Registry**: CLI templates loaded from config (claude_code, opencode, codex, gemini, etc.)
- **Dynamic Directory**: Users specify work directory when creating sessions
- **Per-User Isolation**: Sessions isolated by `user_id` from Feishu
- **Multiple Concurrent Sessions**: Same user can maintain multiple sessions

### New Session Commands (Planned)
```
/template list                    # List available templates
/template show <name>             # Show template details
/session new <template> <path> [name]  # Create new session
/session list                     # List user's sessions
/session use <session_id>         # Switch active session
/session info <session_id>        # Show session details
/session stop <session_id>        # Stop session
/session restart <session_id>     # Restart session
/session rm <session_id>          # Delete session
```

### Direct Session Messaging (Planned)
```
@sid:s_002 fix the failing tests   # Send to specific session
```

### Security Boundaries
- Path must be within `allowed_work_roots` whitelist
- `max_sessions_per_user` limit
- Templates from server config only (no arbitrary command execution)
- Sessions isolated by `user_id`

### Implementation Plan
See `docs/plans/2026-03-12-feishu-multi-session-agent.md` for the full TDD-based implementation plan with 7 tasks:
1. Template Registry and Config Validation
2. Session Persistence and Per-User Session Manager
3. Generic Command Agent and Launch Spec Wiring
4. Feishu Message Parsing for Session Commands
5. Replace Single-Agent Service Wiring with Session Routing
6. Persist Session Metadata
7. Verification and Manual Smoke Checks
