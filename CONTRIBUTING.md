# Contributing to Feishu Agent Bridge

[English](#english) | [中文](#中文)

---

## English

Thank you for your interest in contributing to Feishu Agent Bridge! This document provides guidelines for contributing to the project.

### How to Contribute

#### Reporting Bugs

If you find a bug, please create an issue with the following information:

- **Description**: Clear description of the bug
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Expected Behavior**: What you expected to happen
- **Actual Behavior**: What actually happened
- **Environment**: OS, Python version, Agent version
- **Logs**: Relevant log excerpts (remove sensitive information)

#### Suggesting Features

Feature suggestions are welcome! Please create an issue with:

- **Use Case**: Why this feature would be useful
- **Proposed Solution**: How you envision the feature working
- **Alternatives**: Any alternative solutions you've considered

#### Pull Requests

1. **Fork the Repository**
   ```bash
   git clone https://github.com/yourusername/feishu-agent-bridge.git
   cd feishu-agent-bridge
   ```

2. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make Changes**
   - Follow the existing code style
   - Add tests for new features
   - Update documentation as needed

4. **Test Your Changes**
   ```bash
   # Run tests
   python -m pytest tests/
   
   # Check code style
   flake8 src/
   black src/
   ```

5. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `style:` - Code style changes (formatting, etc.)
   - `refactor:` - Code refactoring
   - `test:` - Adding or updating tests
   - `chore:` - Maintenance tasks

6. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a Pull Request on GitHub.

### Development Setup

1. **Install Dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

2. **Configure Environment**
   ```bash
   cp config/config.yaml.example config/config.yaml
   # Edit config.yaml with your settings
   ```

3. **Run Tests**
   ```bash
   python -m pytest tests/ -v
   ```

### Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Write docstrings for functions and classes
- Keep functions focused and small
- Use meaningful variable names

### Project Structure

```
src/
├── feishu/          # Feishu bot integration
├── agent/           # Agent adapters
├── terminal/        # Terminal/PTY management
├── monitor/         # Status monitoring
├── storage/         # Data storage
└── utils/           # Utility functions
```

### Testing

- Write unit tests for new features
- Ensure all tests pass before submitting PR
- Aim for good test coverage

### Documentation

- Update README.md if adding new features
- Add docstrings to new functions/classes
- Update configuration examples if needed

### Questions?

Feel free to open an issue for any questions or discussions!

---

## 中文

感谢你对 Feishu Agent Bridge 项目的关注！本文档提供了贡献指南。

### 如何贡献

#### 报告 Bug

如果你发现了 bug，请创建一个 issue 并包含以下信息：

- **描述**：清晰的 bug 描述
- **复现步骤**：详细的复现步骤
- **期望行为**：你期望发生什么
- **实际行为**：实际发生了什么
- **环境**：操作系统、Python 版本、Agent 版本
- **日志**：相关的日志摘录（移除敏感信息）

#### 功能建议

欢迎提出功能建议！请创建 issue 并包含：

- **使用场景**：为什么这个功能有用
- **建议方案**：你设想的功能实现方式
- **替代方案**：你考虑过的其他解决方案

#### Pull Request

1. **Fork 仓库**
   ```bash
   git clone https://github.com/yourusername/feishu-agent-bridge.git
   cd feishu-agent-bridge
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **进行修改**
   - 遵循现有的代码风格
   - 为新功能添加测试
   - 根据需要更新文档

4. **测试你的修改**
   ```bash
   # 运行测试
   python -m pytest tests/
   
   # 检查代码风格
   flake8 src/
   black src/
   ```

5. **提交修改**
   ```bash
   git add .
   git commit -m "feat: 添加你的功能描述"
   ```

   遵循 [约定式提交](https://www.conventionalcommits.org/zh-hans/)：
   - `feat:` - 新功能
   - `fix:` - Bug 修复
   - `docs:` - 文档变更
   - `style:` - 代码风格变更（格式化等）
   - `refactor:` - 代码重构
   - `test:` - 添加或更新测试
   - `chore:` - 维护任务

6. **推送并创建 PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   然后在 GitHub 上创建 Pull Request。

### 开发环境设置

1. **安装依赖**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

2. **配置环境**
   ```bash
   cp config/config.yaml.example config/config.yaml
   # 编辑 config.yaml 填写你的配置
   ```

3. **运行测试**
   ```bash
   python -m pytest tests/ -v
   ```

### 代码风格

- 遵循 PEP 8 规范
- 适当使用类型提示
- 为函数和类编写文档字符串
- 保持函数专注和简洁
- 使用有意义的变量名

### 项目结构

```
src/
├── feishu/          # 飞书机器人集成
├── agent/           # Agent 适配器
├── terminal/        # 终端/PTY 管理
├── monitor/         # 状态监控
├── storage/         # 数据存储
└── utils/           # 工具函数
```

### 测试

- 为新功能编写单元测试
- 提交 PR 前确保所有测试通过
- 追求良好的测试覆盖率

### 文档

- 添加新功能时更新 README.md
- 为新函数/类添加文档字符串
- 根据需要更新配置示例

### 有问题？

欢迎创建 issue 进行讨论！
