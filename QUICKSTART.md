# 快速启动指南

## 环境要求

- Python 3.10+
- Claude Code CLI 或 OpenCode CLI
- 飞书企业自建应用（需管理员权限）

---

## 第一步：配置

### 1.1 复制配置文件

```bash
cp config/config.yaml.example config/config.yaml
```

### 1.2 编辑 `config/config.yaml`

```yaml
feishu:
  # 从飞书开放平台获取
  app_id: "your_app_id_here"
  app_secret: "your_app_secret_here"

  # 连接模式：websocket（推荐，无需公网访问）
  connection_mode: "websocket"

  # 服务端口
  server_port: 9980

  # 允许的用户ID列表（留空则允许所有用户）
  allowed_users: []
```

### 1.3 配置工作目录白名单

> **重要**：工作目录必须在白名单范围内，否则无法创建会话。

```yaml
agent:
  allowed_work_roots:
    - "E:\\2026"        # 改成你的实际路径
    - "D:\\workspace"  # 可以添加多个路径
```

---

## 第二步：启动服务

**Windows：**

```batch
start.bat
```

**Linux/Mac：**

```bash
chmod +x start.sh
./start.sh
```

启动成功后会看到：

```
============================================================
  飞书 Agent Bridge 服务 (多会话版)
============================================================

飞书配置:
   App ID: cli_xxx
   连接模式: websocket
   服务端口: 9980
   允许用户: 所有用户

[OK] 会话管理器已初始化
[OK] 服务启动完成，等待飞书消息...
```

---

## 第三步：创建会话

在飞书中向机器人发送命令：

### 查看可用模板

```
/template list
```

响应：
```
📋 可用模板:
  • claude_code: claude
  • opencode: opencode
  • codex: codex
```

### 创建新会话

```
/session new claude_code E:\2026\my_project 我的项目
```

响应：
```
✅ 会话已创建: s_001
模板: claude_code
目录: E:\2026\my_project
名称: 我的项目
```

### 开始对话

```
帮我创建一个 Python FastAPI 项目
```

机器人会将消息转发给 Claude Code 并返回结果。

---

## 命令参考

### 会话命令

| 命令 | 说明 |
|------|------|
| `/session new <模板> <路径> [名称]` | 创建新会话 |
| `/session list` | 列出所有会话 |
| `/session use <会话ID>` | 切换活动会话 |
| `/session info <会话ID>` | 查看会话详情 |
| `/session stop <会话ID>` | 停止会话 |
| `/session restart <会话ID>` | 重启会话 |
| `/session rm <会话ID>` | 删除会话 |

### 模板命令

| 命令 | 说明 |
|------|------|
| `/template list` | 列出可用模板 |
| `/template show <名称>` | 查看模板详情 |

### 通用命令

| 命令 | 说明 |
|------|------|
| `/status` | 查看状态 |
| `/stop` | 停止服务 |
| `/help` | 显示帮助 |

### 定向消息

| 格式 | 说明 |
|------|------|
| `@sid:<会话ID> <消息>` | 向指定会话发送消息（不依赖活动会话） |

---

## 目录白名单限制

工作目录必须满足以下条件之一：

1. 目录路径在 `allowed_work_roots` 配置的某个根目录下
2. 使用相对路径时，相对的基准目录在白名单中

**示例配置：**

```yaml
agent:
  allowed_work_roots:
    - "E:\\2026"
```

**允许的路径：**
- `E:\2026\my_project`
- `E:\2026\repo\api`
- `E:\2026\test.py`（文件也可以）

**不允许的路径：**
- `C:\Users\admin`
- `D:\other_project`

---

## 飞书应用配置

如果尚未创建飞书应用：

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 启用机器人功能
4. 获取 `App ID` 和 `App Secret`
5. 申请权限：
   - `im:message` - 获取和发送消息
   - `im:message:send_as_bot` - 以机器人身份发送消息
6. 如果使用 Webhook 模式，还需配置事件订阅

---

## 故障排查

### Agent 无法启动

1. 检查 CLI 是否安装：
   ```bash
   claude --version
   opencode --version
   ```

2. 检查配置文件中的命令路径

3. 查看日志文件：`logs/agent_bridge_YYYYMMDD.log`

### 收不到飞书消息

1. 确认 `connection_mode` 配置正确（建议用 websocket）
2. 检查 `allowed_users` 是否包含你的用户ID
3. 查看飞书开放平台的事件日志

### 会话创建失败

1. 确认工作目录在 `allowed_work_roots` 白名单中
2. 确认模板名称正确（`/template list` 可查看）
3. 检查是否达到会话数上限（默认 5 个）
