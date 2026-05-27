# X-Agent 快速操作指南

这是一个快速参考指南，包含常用的操作命令和工作流程。

---

## 🚀 快速开始

### 首次设置

```bash
# 1. 克隆仓库
git clone <repository-url>
cd x-agent-core

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 生成安全密钥
python scripts/generate_secrets.py

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env，替换所有密钥占位符

# 6. 初始化 Git Flow
python scripts/init_git_flow.py

# 7. 安装 pre-commit hooks
pre-commit install

# 8. 启动服务
docker-compose up -d
python -m backend.app.core.migration init
```

---

## 🔒 安全操作

### 生成新密钥

```bash
# 生成所有密钥
python scripts/generate_secrets.py

# 输出示例：
# JWT_SECRET=<64-char-random-string>
# ENCRYPTION_KEY=<32-byte-hex-string>
# NEO4J_PASSWORD=<32-char-password>
# S3_ACCESS_KEY=<24-char-key>
# S3_SECRET_KEY=<48-char-key>
```

### 运行安全审计

```bash
# 扫描代码中的安全问题
python scripts/security_audit.py

# 检查 Git 历史中的敏感信息
git log -p | grep -i "password\|secret\|key\|token"

# 使用 pre-commit 检查
pre-commit run detect-secrets --all-files
```

---

## 🌿 Git 工作流

### 创建新功能

```bash
# 1. 切换到 develop 分支
git checkout develop
git pull origin develop

# 2. 创建功能分支
git checkout -b feature/your-feature-name

# 3. 开发并提交
git add .
git commit -m "feat: add your feature description"

# 4. 推送到远程
git push origin feature/your-feature-name

# 5. 在 GitHub/GitLab 创建 PR
# 目标分支: develop
```

### 修复 Bug

```bash
# 从 develop 创建 bugfix 分支
git checkout develop
git checkout -b bugfix/issue-description

# 提交修复
git commit -m "fix: resolve issue description"

# 推送并创建 PR
git push origin bugfix/issue-description
```

### 紧急修复（Hotfix）

```bash
# 从 main 创建 hotfix 分支
git checkout main
git checkout -b hotfix/critical-issue

# 修复并提交
git commit -m "fix: critical issue description"

# 推送并创建 PR 到 main
git push origin hotfix/critical-issue
```

### 提交消息规范

```bash
# 格式: <type>(<scope>): <subject>

# 类型:
feat: 新功能
fix: Bug 修复
docs: 文档更新
style: 代码格式（不影响逻辑）
refactor: 代码重构
test: 测试相关
chore: 构建/工具/依赖更新

# 示例:
git commit -m "feat(agent): add multi-step reasoning"
git commit -m "fix(memory): resolve vector search timeout"
git commit -m "docs(api): update authentication guide"
```

---

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_agent_loop.py

# 运行特定测试
pytest tests/test_agent_loop.py::test_agent_initialization

# 运行匹配模式的测试
pytest -k "test_memory"

# 详细输出
pytest -v

# 显示打印输出
pytest -s
```

### 测试覆盖率

```bash
# 生成覆盖率报告
pytest --cov=backend --cov-report=html

# 查看报告
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
xdg-open htmlcov/index.html  # Linux

# 只显示覆盖率
pytest --cov=backend --cov-report=term-missing
```

---

## 🔍 代码质量

### 代码检查

```bash
# 运行 Ruff 检查
ruff check .

# 自动修复问题
ruff check --fix .

# 格式化代码
ruff format .

# 类型检查
mypy backend/

# 运行所有 pre-commit 检查
pre-commit run --all-files
```

### 代码复杂度分析

```bash
# 安装 radon
pip install radon

# 分析圈复杂度
radon cc backend/ -a -nb

# 分析可维护性指数
radon mi backend/ -nb

# 查找复杂函数
radon cc backend/ -nc -s
```

---

## 🐳 Docker 操作

### 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 启动特定服务
docker-compose up -d postgres qdrant

# 查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
```

### 管理服务

```bash
# 停止服务
docker-compose stop

# 重启服务
docker-compose restart

# 重启特定服务
docker-compose restart backend

# 删除容器和卷
docker-compose down -v

# 重建镜像
docker-compose build --no-cache
```

---

## 🗄️ 数据库操作

### PostgreSQL

```bash
# 连接到数据库
docker-compose exec postgres psql -U xagent -d xagent

# 运行迁移
python -m backend.app.core.migration init
python -m backend.app.core.migration upgrade

# 创建新迁移
alembic revision -m "description"

# 回滚迁移
alembic downgrade -1
```

### Qdrant（向量数据库）

```bash
# 访问 Qdrant Web UI
open http://localhost:6333/dashboard

# 使用 Python 客户端
python
>>> from qdrant_client import QdrantClient
>>> client = QdrantClient(url="http://localhost:6333")
>>> client.get_collections()
```

---

## 🚀 运行应用

### 开发模式

```bash
# 启动后端服务器（带热重载）
uvicorn backend.app.web:app --reload --host 0.0.0.0 --port 8000

# 启动工作流 worker
python -m backend.app.workflow_worker

# 设置日志级别
LOG_LEVEL=DEBUG uvicorn backend.app.web:app --reload
```

### 生产模式

```bash
# 使用 Gunicorn
gunicorn backend.app.web:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000

# 使用 Docker
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📊 监控和调试

### 查看日志

```bash
# 应用日志
tail -f logs/xagent.log

# Docker 日志
docker-compose logs -f backend

# 实时日志（带过滤）
docker-compose logs -f | grep ERROR
```

### 性能分析

```bash
# 使用 cProfile
python -m cProfile -o profile.stats backend/app/web.py

# 分析结果
python -m pstats profile.stats
>>> sort cumulative
>>> stats 20

# 使用 py-spy（实时分析）
pip install py-spy
py-spy top --pid <process-id>
```

---

## 🔧 常见问题解决

### 依赖问题

```bash
# 重新安装依赖
pip install --force-reinstall -e ".[dev]"

# 清理缓存
pip cache purge
rm -rf __pycache__ .pytest_cache .mypy_cache

# 更新依赖
pip install --upgrade -e ".[dev]"
```

### 数据库问题

```bash
# 重置数据库
docker-compose down -v
docker-compose up -d postgres
python -m backend.app.core.migration init

# 检查连接
docker-compose exec postgres pg_isready
```

### Git 问题

```bash
# 撤销最后一次提交（保留更改）
git reset --soft HEAD~1

# 撤销最后一次提交（丢弃更改）
git reset --hard HEAD~1

# 清理未跟踪的文件
git clean -fd

# 同步远程分支
git fetch --prune
```

---

## 📚 有用的命令

### 项目信息

```bash
# 查看项目结构
tree -L 3 -I '__pycache__|*.pyc|.git'

# 统计代码行数
find backend -name "*.py" | xargs wc -l

# 查找 TODO 注释
grep -r "TODO\|FIXME\|XXX" backend/
```

### 环境信息

```bash
# Python 版本
python --version

# 已安装包
pip list

# 环境变量
env | grep XAGENT

# 系统信息
uname -a
```

---

## 🔗 快速链接

- **文档**: `docs/README.md`
- **API 文档**: `http://localhost:8000/docs`
- **Qdrant UI**: `http://localhost:6333/dashboard`
- **Langfuse**: `http://localhost:3000`

---

## 📞 获取帮助

- **GitHub Issues**: 报告 Bug 或请求功能
- **GitHub Discussions**: 提问和讨论
- **文档**: 查看 `docs/` 目录
- **Email**: dev@x-agent.dev

---

**提示**: 将此文件加入书签，方便快速查找命令！
