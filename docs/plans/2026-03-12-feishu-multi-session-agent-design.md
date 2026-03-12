# Feishu Multi-Session Agent Design

**Date:** 2026-03-12

**Status:** Approved

## Goal

将当前“单飞书机器人对应单个固定目录 Agent 进程”的桥接服务，升级为“每个飞书用户拥有独立会话池，可在飞书中临时指定目录并按模板启动不同 CLI Agent，会话可并存并持续交互”。

## Current State

当前项目已经具备以下能力：

- 飞书消息接入与事件处理
- 单个 Agent 进程的生命周期管理
- Claude Code 与 OpenCode 两种固定 Agent 适配
- 固定 `work_dir` 启动
- `/status`、`/switch`、`/restart`、`/stop`、`/help` 等系统命令

当前限制：

- 只能运行一个 Agent
- 工作目录是配置中的固定值
- 不支持多会话并存
- 不支持按飞书用户隔离状态
- 不支持基于模板扩展更多 CLI

## Confirmed Requirements

- 路径由飞书侧临时指定并切换，不修改全局默认目录
- 同一飞书用户可同时维护多个会话
- 不同飞书用户的会话池完全隔离
- CLI 类型支持自定义模板，而不是只支持固定枚举值

## Architecture

### Session Model

新增 `SessionManager` 负责用户级会话编排，核心结构如下：

- `user_id -> UserSessionPool`
- `UserSessionPool`
  - `sessions: dict[session_id, AgentSession]`
  - `active_session_id`
- `AgentSession`
  - `session_id`
  - `session_name`
  - `template_name`
  - `work_dir`
  - `agent`
  - `status`
  - `created_at`
  - `last_active_at`

`AgentBridgeService` 不再直接持有单个 `self.agent`。它改为：

- 从飞书消息中提取 `user_id`
- 查询该用户的 `UserSessionPool`
- 将普通消息路由到该用户的活动会话
- 将带显式会话标识的消息路由到指定会话

### Agent Abstraction

保留当前 `BaseAgent` 的进程管理能力，不重写底层 PTY 和收发逻辑。

新增一个模板驱动的通用 Agent 实例化路径，例如 `TemplateAgent` 或 `CommandAgent`，用于：

- 根据模板生成 `command` 与 `args`
- 设置工作目录
- 注入模板定义的环境变量
- 复用现有输出过滤与状态能力

现有 `claude_code`、`opencode` 可以逐步迁移为默认模板，而不是长期保留为硬编码特例。

### Template Registry

新增 `TemplateRegistry`，从配置文件加载全局模板定义，负责：

- 获取模板
- 校验模板存在
- 展开变量
- 生成最终启动参数

模板定义建议字段：

- `command`
- `args`
- `env`
- `append_prompt_as_stdin`
- `startup_mode`
- `output_filter_profile`

第一版只要求真正用到的字段落地，避免过度设计。

## Feishu Command Design

### Template Commands

- `/template list`
  - 列出可用模板、底层命令和简要说明
- `/template show <name>`
  - 查看单个模板展开前的配置摘要

第一版不支持飞书侧在线编辑模板，模板定义权保留在服务端配置文件。

### Session Commands

- `/session new <template> <path> [session_name]`
  - 创建新会话并启动底层 CLI
- `/session list`
  - 列出当前飞书用户的会话
- `/session use <session_id>`
  - 切换当前活动会话
- `/session info <session_id>`
  - 查看会话详情
- `/session stop <session_id>`
  - 停止会话进程但保留记录
- `/session restart <session_id>`
  - 使用原模板与原目录重启
- `/session rm <session_id>`
  - 删除会话，若仍在运行则先停止

### Message Routing

- 普通文本默认发给当前活动会话
- 支持 `@sid:<session_id> <message>` 直接发给指定会话
- Agent 输出建议增加会话前缀，例如：
  - `[api-fix|codex|running] ...`

### Operational Commands

- `/status`
  - 展示当前用户会话池摘要，而不是单 Agent 状态
- `/help`
  - 更新为新的模板/会话命令说明

现有 `/switch` 这类全局单 Agent 模式命令应移除或兼容为废弃提示。

## Configuration Design

配置分为全局运行配置与模板注册表两层。

示例：

```yaml
agent:
  default_timeout: 30
  max_sessions_per_user: 5
  allowed_work_roots:
    - E:\2026
    - D:\workspace

templates:
  claude_code:
    command: claude
    args: ["code"]
    env: {}
    append_prompt_as_stdin: true

  codex:
    command: codex
    args: []
    env: {}
    append_prompt_as_stdin: true

  opencode:
    command: opencode
    args: []
    env: {}
    append_prompt_as_stdin: true

  gemini:
    command: gemini
    args: []
    env: {}
    append_prompt_as_stdin: true
```

### Supported Template Variables

第一版建议仅支持安全且必要的字符串替换变量：

- `${work_dir}`
- `${session_id}`
- `${user_id}`
- `${session_name}`

替换方式为参数级字符串替换，不允许把整条命令拼成 shell 字符串交由解释器执行。

## Security Boundaries

远程指定目录能力必须带边界控制。第一版建议强制以下校验：

- 路径存在且是目录
- 路径位于 `allowed_work_roots` 白名单下
- 每个用户受 `max_sessions_per_user` 限制

模板定义仅来自服务端配置文件，不允许飞书侧动态提交任意命令模板。

用户隔离仅基于飞书 `user_id`：

- 会话记录不可跨用户可见
- 活动会话不可跨用户切换
- 会话控制不可跨用户操作

## Persistence Strategy

第一版建议：

- 模板配置持久化在 `config.yaml`
- 会话元数据持久化到现有存储层
- 服务重启后不自动恢复运行中的 CLI 进程

恢复行为：

- 重启后历史会话仍可见
- 历史会话状态标记为 `stopped`
- 用户通过 `/session restart <session_id>` 手动恢复

## Error Handling

错误类型分为四类：

### Parameter Errors

包括：

- 模板不存在
- 路径缺失
- `session_id` 不存在
- 命令格式错误

处理策略：

- 返回简明错误与正确用法

### Environment Errors

包括：

- CLI 命令不存在
- 工作目录不可访问
- 启动超时

处理策略：

- 返回明确失败原因
- 启动失败的会话不进入运行态

### Runtime Errors

包括：

- CLI 异常退出
- PTY 断开
- 写入失败

处理策略：

- 会话状态切换为 `stopped` 或 `crashed`
- 后续消息提示用户执行重启

### Boundary Errors

包括：

- 路径越界
- 会话数超限
- 跨用户访问

处理策略：

- 拒绝请求并明确说明原因

建议统一错误消息前缀，例如：

- `[session:new] failed: path is outside allowed roots`
- `[session:use] failed: session s_123 not found`

## Testing Strategy

### Unit Tests

测试重点：

- 模板加载与变量替换
- 路径白名单校验
- 用户隔离逻辑
- 会话状态流转

### Service Tests

测试 `SessionManager` 的核心能力：

- `new`
- `list`
- `use`
- `send`
- `stop`
- `restart`
- `rm`

底层 Agent 应使用 fake/mock 实现，避免依赖真实 CLI。

### Command Parsing Tests

测试飞书输入解析与路由：

- `/session new ...`
- `/session use ...`
- `/session list`
- `@sid:<session_id> ...`
- 无活动会话时的普通文本

### Manual Integration

第一版不将真实 `claude`、`codex`、`opencode`、`gemini` 集成测试纳入自动测试。

原因：

- 本地安装依赖不稳定
- 登录态与权限因环境而异
- CLI 交互差异较大

真实联调通过手工验证完成。

## Scope

### In Scope

- 多用户独立会话池
- 多会话并存
- 服务端配置模板
- 飞书侧按模板和目录创建会话
- 当前活动会话与 `@sid:` 定向发送
- 会话生命周期管理
- 重启后保留会话记录但不自动恢复进程

### Out of Scope

- 飞书侧在线编辑模板
- 自动恢复运行中进程
- 跨用户共享会话
- 复杂 ACL
- 每种 CLI 的深度定制插件系统

## Recommended Implementation Direction

第一版应尽量复用现有工程能力，避免重写：

- 保留 `BaseAgent` 的进程与输出处理能力
- 新增 `TemplateRegistry` 与 `SessionManager`
- 调整 `AgentBridgeService` 为基于用户和会话的路由器
- 将现有命令处理迁移为多会话命令模型

这个方向改动集中、可验证、风险可控，也最符合当前代码基础。
