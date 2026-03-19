# Feishu Agent Bridge

[English](#english) | [中文](#中文)

[![Demo Video](https://img.shields.io/badge/Demo-YouTube-red?logo=youtube)](https://youtu.be/TpqevBNgQhI)

---

## English

### Overview

Feishu Agent Bridge is a service that connects Feishu (Lark) bots with AI coding assistants (Claude Code/OpenCode), enabling remote control of AI programming tools through Feishu messaging.

**📺 [Watch Demo Video](https://youtu.be/TpqevBNgQhI)**

### Key Features

- 🤖 **Feishu Bot Integration** - Interact with AI agents through Feishu messages
- 🔍 **Intelligent Output Filtering** - Forward only critical information (confirmations, errors, results)
- 🔄 **Bidirectional Real-time Communication** - Support for command sending and result receiving
- 📊 **Status Monitoring** - Timeout alerts, heartbeat detection
- 🎯 **Multi-Agent Support** - Compatible with Claude Code and OpenCode
- 📱 **Web Dashboard** - Real-time chat history and statistics
- 💾 **Chat History Storage** - Automatic conversation logging
- 🔌 **Dual Connection Modes** - WebSocket (long connection) or Webhook callback
- 🏢 **Multi-Session Per User** - Each user can have multiple independent sessions with different templates

### Architecture

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────┐
│   Feishu    │◄───────►│  Agent Bridge    │◄───────►│ Claude Code │
│   (Lark)    │         │   (This Service) │         │  /OpenCode  │
└─────────────┘         └──────────────────┘         └─────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │ Web Dashboard│
                        └──────────────┘
```

### Quick Start

#### Prerequisites

- Python 3.10+
- Claude Code CLI or OpenCode CLI
- Feishu Enterprise Self-built Application (requires admin privileges)

#### Installation

**Windows:**

```batch
# Clone the repository
git clone https://github.com/yourusername/feishu-agent-bridge.git
cd feishu-agent-bridge

# Run the startup script (automatically creates virtual environment and installs dependencies)
start.bat
```

**Linux/Mac:**

```bash
# Clone the repository
git clone https://github.com/yourusername/feishu-agent-bridge.git
cd feishu-agent-bridge

# Add execute permission
chmod +x start.sh

# Run the startup script
./start.sh
```

#### Configuration

1. Copy the configuration template:
```bash
cp config/config.yaml.example config/config.yaml
```

2. Edit `config/config.yaml` and fill in the following information:

```yaml
feishu:
  app_id: "your_app_id"           # Feishu App ID
  app_secret: "your_app_secret"   # Feishu App Secret
  connection_mode: "websocket"    # Connection mode: websocket or webhook
  server_port: 9980               # Service listening port
  allowed_users:                  # Allowed user OpenIDs (optional)
    - "ou_xxxxxxxxxxxxx"

agent:
  default: "claude_code"          # Agent to use
  claude_code:
    command: "claude"             # Claude Code command path
    work_dir: "/path/to/project"  # Working directory
    args: ["--dangerously-skip-permissions"]
```

#### Feishu Application Setup

1. Visit [Feishu Open Platform](https://open.feishu.cn/)
2. Create an enterprise self-built application
3. Enable bot functionality
4. Configure event subscription (for webhook mode):
   - Request URL: `http://your-domain:9980/feishu/event`
   - Subscribe to event: `im.message.receive_v1`
5. Apply for permissions:
   - `im:message` - Get and send messages
   - `im:message:send_as_bot` - Send messages as bot
6. Get credentials and fill in `config.yaml`

**Note:** WebSocket mode (recommended) doesn't require public URL configuration.

### Usage

#### Start the Service

```bash
# Windows
start.bat

# Linux/Mac
./start.sh
```

#### Interact via Feishu

Send messages to the bot in Feishu:

```
User: Help me create a Python FastAPI project

Bot: ⏳ Progress
     Creating project structure...

Bot: ❓ Confirmation Required
     I'll create the following files:
     - main.py
     - requirements.txt
     Do you want me to proceed? (y/n)

User: yes

Bot: ✅ Result
     Created 2 files successfully!
```

#### System Commands

**Session Commands:**
- `/session new <模板> <路径> [名称]` - Create a new session
- `/session list` - List all sessions
- `/session use <会话ID>` - Switch active session
- `/session info <会话ID>` - Show session details
- `/session stop <会话ID>` - Stop a session
- `/session restart <会话ID>` - Restart a session
- `/session rm <会话ID>` - Delete a session

**Template Commands:**
- `/template list` - List available templates
- `/template show <名称>` - Show template details

**General Commands:**
- `/status` - View current status
- `/stop` - Stop service
- `/help` - Show help information

**Directed Messages:**
- `@sid:<会话ID> <消息>` - Send message to a specific session (bypasses active session)

#### Web Dashboard

Visit `http://localhost:9980/` to view real-time chat history and statistics.

### Project Structure

```
feishu-agent-bridge/
├── config/
│   ├── config.yaml.example      # Configuration template
│   └── config.yaml              # Actual configuration (not committed)
├── src/
│   ├── main.py                  # Main entry point
│   ├── feishu/                  # Feishu bot module
│   │   ├── bot.py               # Feishu API integration
│   │   ├── lark_client.py       # Lark SDK client
│   │   ├── message_handler.py   # Message parsing for session commands
│   │   └── websocket_client.py  # WebSocket client
│   ├── agent/                   # Agent adapters
│   │   ├── base.py              # Agent base class
│   │   ├── claude_code.py       # Claude Code adapter
│   │   ├── opencode.py          # OpenCode adapter
│   │   ├── command_agent.py     # Generic template-driven agent
│   │   ├── template_registry.py # Template registry with variable expansion
│   │   └── output_filter.py     # Output filter
│   ├── session/                 # Session management
│   │   ├── manager.py           # Per-user session pool manager
│   │   └── models.py           # Session data models
│   ├── terminal/                # Terminal management
│   │   └── pty_manager.py       # PTY process manager
│   ├── monitor/                 # Monitoring module
│   │   └── status_monitor.py    # Status monitor
│   ├── storage/                 # Storage module
│   │   └── chat_store.py        # Chat history and session record storage
│   └── utils/                   # Utility module
│       └── logger.py            # Logger utility
├── web/
│   └── dashboard.html           # Web dashboard
├── tests/                       # Test suite
│   ├── agent/                   # Agent tests
│   ├── feishu/                 # Feishu module tests
│   ├── session/                # Session tests
│   └── service/                # Service integration tests
├── logs/                        # Log directory
├── data/                        # Data directory (chat logs, session records)
├── requirements.txt             # Python dependencies
└── README.md                    # Project documentation
```

### Core Features

#### Intelligent Output Filtering

The OutputFilter automatically identifies and forwards the following types of messages to Feishu:

- ❓ **Confirmation Requests** - Operations requiring user confirmation
- ❌ **Error Messages** - Execution failures or exceptions
- ✅ **Execution Results** - Operation completion results
- ⏳ **Progress Information** - Progress of long-running operations

Filtered content:
- Thinking process
- Loading animations
- Debug information
- Empty lines and separators

#### Status Monitoring

- Real-time agent process status monitoring
- Command execution timeout detection (default 5 minutes)
- Periodic heartbeat
- Automatic alerts to Feishu on exceptions

#### Chat History

- Automatically save all conversations to JSONL files
- Store by date
- Query via Web API
- Provide statistics

### Troubleshooting

#### Agent Cannot Start

1. Check if Claude Code/OpenCode is installed:
   ```bash
   claude --version
   opencode --version
   ```

2. Verify the command path in the configuration file

3. Check log files: `logs/agent_bridge_YYYYMMDD.log`

#### Cannot Receive Feishu Messages

1. Verify event subscription URL is correct
2. Ensure service port (default 9980) is accessible
3. Check Feishu Open Platform event logs
4. Verify `allowed_users` configuration

#### Inaccurate Output Filtering

Edit `output_filter` configuration in `config/config.yaml`:

```yaml
output_filter:
  forward_patterns:
    - "your_custom_pattern"
  ignore_patterns:
    - "pattern_to_ignore"
```

### Security Recommendations

1. **Do not commit `config/config.yaml` to version control**
2. Use `allowed_users` to restrict access
3. Use HTTPS and encryption in production
4. Regularly update dependencies
5. Store sensitive information in environment variables

### Development

#### Run Tests

```bash
python -m pytest tests/
```

#### Code Linting

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run linter
flake8 src/
black src/
```

### License

MIT License

### Contributing

Issues and Pull Requests are welcome!

### Repository

- GitHub: https://github.com/parleychou/MiniOpenClaw
- Issues: https://github.com/parleychou/MiniOpenClaw/issues

---

## 中文

### 项目简介

飞书 Agent Bridge 是一个连接飞书机器人与 AI 编程助手（Claude Code/OpenCode）的桥接服务，让你可以通过飞书消息远程控制 AI 编程工具。

**📺 [观看演示视频](https://youtu.be/TpqevBNgQhI)**

### 核心功能

- 🤖 **飞书机器人集成** - 通过飞书消息与 AI Agent 交互
- 🔍 **智能输出过滤** - 只转发关键信息（确认请求、错误、结果）
- 🔄 **双向实时通信** - 支持命令发送和结果接收
- 📊 **状态监控** - 超时告警、心跳检测
- 🎯 **多 Agent 支持** - 兼容 Claude Code 和 OpenCode
- 📱 **Web 仪表板** - 实时查看聊天记录和统计
- 💾 **聊天记录存储** - 自动保存所有对话历史
- 🔌 **双连接模式** - WebSocket（长连接）或 Webhook 回调
- 🏢 **多会话支持** - 每个用户可同时运行多个独立会话，使用不同模板

### 架构设计

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────┐
│    飞书     │◄───────►│  Agent Bridge    │◄───────►│ Claude Code │
│   (Lark)    │         │   (本服务)        │         │  /OpenCode  │
└─────────────┘         └──────────────────┘         └─────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  Web 控制台  │
                        └──────────────┘
```

### 快速开始

#### 环境要求

- Python 3.10+
- Claude Code CLI 或 OpenCode CLI
- 飞书企业自建应用（需要管理员权限）

#### 安装

**Windows:**

```batch
# 克隆项目
git clone https://github.com/yourusername/feishu-agent-bridge.git
cd feishu-agent-bridge

# 运行启动脚本（会自动创建虚拟环境和安装依赖）
start.bat
```

**Linux/Mac:**

```bash
# 克隆项目
git clone https://github.com/yourusername/feishu-agent-bridge.git
cd feishu-agent-bridge

# 添加执行权限
chmod +x start.sh

# 运行启动脚本
./start.sh
```

#### 配置

1. 复制配置文件模板：
```bash
cp config/config.yaml.example config/config.yaml
```

2. 编辑 `config/config.yaml`，填写以下信息：

```yaml
feishu:
  app_id: "your_app_id"           # 飞书应用 ID
  app_secret: "your_app_secret"   # 飞书应用密钥
  connection_mode: "websocket"    # 连接模式：websocket 或 webhook
  server_port: 9980               # 服务监听端口
  allowed_users:                  # 允许的用户 OpenID（可选）
    - "ou_xxxxxxxxxxxxx"

agent:
  default: "claude_code"          # 使用的 Agent
  claude_code:
    command: "claude"             # Claude Code 命令路径
    work_dir: "/path/to/project"  # 工作目录
    args: ["--dangerously-skip-permissions"]
```

#### 飞书应用配置

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 启用机器人功能
4. 配置事件订阅（webhook 模式需要）：
   - 请求地址：`http://your-domain:9980/feishu/event`
   - 订阅事件：`im.message.receive_v1`
5. 申请权限：
   - `im:message` - 获取和发送消息
   - `im:message:send_as_bot` - 以机器人身份发送消息
6. 获取凭证并填入 `config.yaml`

**注意：** WebSocket 模式（推荐）无需配置公网 URL。

### 使用方法

#### 启动服务

```bash
# Windows
start.bat

# Linux/Mac
./start.sh
```

#### 飞书端交互

在飞书中向机器人发送消息：

```
用户: 帮我创建一个 Python FastAPI 项目

机器人: ⏳ 进度
       正在创建项目结构...

机器人: ❓ 需要确认
       我将创建以下文件：
       - main.py
       - requirements.txt
       是否继续？(y/n)

用户: 确认

机器人: ✅ 结果
       成功创建 2 个文件！
```

#### 系统命令

**会话命令：**
- `/session new <模板> <路径> [名称]` - 创建新会话
- `/session list` - 列出会话
- `/session use <会话ID>` - 切换活动会话
- `/session info <会话ID>` - 查看会话详情
- `/session stop <会话ID>` - 停止会话
- `/session restart <会话ID>` - 重启会话
- `/session rm <会话ID>` - 删除会话

**模板命令：**
- `/template list` - 列出可用模板
- `/template show <名称>` - 查看模板详情

**通用命令：**
- `/status` - 查看状态
- `/stop` - 停止服务
- `/help` - 显示帮助信息

**定向消息：**
- `@sid:<会话ID> <消息>` - 向指定会话发送消息（跳过活动会话）

#### Web 仪表板

访问 `http://localhost:9980/` 查看实时聊天记录和统计信息。

### 项目结构

```
feishu-agent-bridge/
├── config/
│   ├── config.yaml.example      # 配置文件模板
│   └── config.yaml              # 实际配置（不提交到 Git）
├── src/
│   ├── main.py                  # 主入口
│   ├── feishu/                  # 飞书机器人模块
│   │   ├── bot.py               # 飞书 API 集成
│   │   ├── lark_client.py       # Lark SDK 客户端
│   │   └── websocket_client.py  # WebSocket 客户端
│   ├── agent/                   # Agent 适配器
│   │   ├── base.py              # Agent 基类
│   │   ├── claude_code.py       # Claude Code 适配器
│   │   ├── opencode.py          # OpenCode 适配器
│   │   └── output_filter.py     # 输出过滤器
│   ├── terminal/                # 终端管理
│   │   └── pty_manager.py       # PTY 进程管理
│   ├── monitor/                 # 监控模块
│   │   └── status_monitor.py    # 状态监控
│   ├── storage/                 # 存储模块
│   │   └── chat_store.py        # 聊天记录存储
│   └── utils/                   # 工具模块
│       └── logger.py            # 日志工具
├── web/
│   └── dashboard.html           # Web 仪表板
├── logs/                        # 日志目录
├── data/                        # 数据目录
├── requirements.txt             # Python 依赖
└── README.md                    # 项目文档
```

### 核心功能说明

#### 智能输出过滤

OutputFilter 会自动识别并转发以下类型的消息到飞书：

- ❓ **确认请求** - 需要用户确认的操作
- ❌ **错误信息** - 执行失败或异常
- ✅ **执行结果** - 操作完成的结果
- ⏳ **进度信息** - 长时间操作的进度

过滤掉的内容：
- 思考过程
- 加载动画
- 调试信息
- 空行和分隔符

#### 状态监控

- 实时监控 Agent 进程状态
- 检测命令执行超时（默认 5 分钟）
- 定期发送心跳
- 异常情况自动告警到飞书

#### 聊天记录

- 自动保存所有对话到 JSONL 文件
- 按日期分文件存储
- 支持通过 Web API 查询
- 提供统计信息

### 故障排查

#### Agent 无法启动

1. 检查 Claude Code/OpenCode 是否已安装：
   ```bash
   claude --version
   opencode --version
   ```

2. 检查配置文件中的命令路径是否正确

3. 查看日志文件：`logs/agent_bridge_YYYYMMDD.log`

#### 飞书消息无法接收

1. 检查事件订阅地址是否正确
2. 确认服务端口（默认 9980）是否可访问
3. 查看飞书开放平台的事件日志
4. 检查 `allowed_users` 配置

#### 输出过滤不准确

编辑 `config/config.yaml` 中的 `output_filter` 配置：

```yaml
output_filter:
  forward_patterns:
    - "your_custom_pattern"
  ignore_patterns:
    - "pattern_to_ignore"
```

### 安全建议

1. **不要将 `config/config.yaml` 提交到版本控制**
2. 使用 `allowed_users` 限制可访问的用户
3. 在生产环境使用 HTTPS 和加密
4. 定期更新依赖包
5. 使用环境变量存储敏感信息

### 开发

#### 运行测试

```bash
python -m pytest tests/
```

#### 代码检查

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行 linter
flake8 src/
black src/
```

### 许可证

MIT License

### 验证说明

**已验证命令：**

| 命令 | 说明 |
|------|------|
| `/template list` | 列出所有可用模板 |
| `/template show <名称>` | 显示模板详情 |
| `/session new <模板> <路径> [名称]` | 创建新会话 |
| `/session list` | 列出用户所有会话 |
| `/session use <会话ID>` | 切换活动会话 |
| `/session info <会话ID>` | 显示会话详情 |
| `/session stop <会话ID>` | 停止会话 |
| `/session restart <会话ID>` | 重启会话 |
| `/session rm <会话ID>` | 删除会话 |
| `@sid:<会话ID> <消息>` | 向指定会话发送消息 |
| `/status` | 显示会话池状态 |
| `/help` | 显示帮助信息 |

**目录白名单限制：**

- 工作目录必须在 `allowed_work_roots` 配置的范围内
- 尝试使用不在白名单的路径将返回错误
- 服务启动时需配置有效的模板和路径

**会话持久化：**

- 会话元数据保存在 `data/sessions.json`
- 服务重启后可通过 `/session list` 查看历史会话状态（需重新启动 agent 进程）

### 贡献

欢迎提交 Issue 和 Pull Request！

### 联系方式

- 项目地址：https://github.com/parleychou/MiniOpenClaw
- 问题反馈：https://github.com/parleychou/MiniOpenClaw/issues
