# X-Agent 云端服务 - 文档索引

**最后更新：** 2026-05-27  
**版本：** 1.0.0

---

## 🗂️ 快速导航

### 📖 开始阅读

1. **[README.md](README.md)** - 项目概览和快速开始
2. **[DELIVERY_SUMMARY.md](DELIVERY_SUMMARY.md)** - 交付总结和统计

### 🏗️ 架构与设计

3. **[CLOUD_ARCHITECTURE.md](CLOUD_ARCHITECTURE.md)** - 完整的云端架构设计
   - 系统架构概览
   - 核心服务模块
   - 数据存储架构
   - 实时同步流程
   - 冲突解决策略
   - 加密与安全
   - 可扩展性设计

### 🔌 API 接口

4. **[OPENAPI_SPEC.md](OPENAPI_SPEC.md)** - OpenAPI 3.0 规范
   - 认证与授权
   - 同步操作 API
   - 冲突解决 API
   - 版本控制 API
   - 加密服务 API
   - WebSocket 实时同步
   - 错误处理
   - 速率限制

### 💾 数据库

5. **[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)** - 数据库设计
   - 核心表设计
   - 关系表设计
   - 审计与日志表
   - 索引策略
   - 分区策略
   - 初始化脚本
   - 备份与恢复

### 🚀 部署

6. **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - 部署指南
   - Docker 部署
   - Kubernetes 部署
   - 监控与日志
   - 备份与恢复
   - 安全加固
   - 性能优化
   - 故障恢复

### 💻 实现

7. **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** - 实现指南
   - 快速开始
   - 核心模块集成
   - 数据库初始化
   - 测试套件
   - 监控与告警
   - 最佳实践
   - 故障排查

### 📦 代码

8. **[sync_service.py](sync_service.py)** - 同步服务实现
   - VectorClock 向量时钟
   - SyncOperation 同步操作
   - ConflictDetector 冲突检测
   - ConflictResolver 冲突解决
   - SyncService 主服务

9. **[encryption_service.py](encryption_service.py)** - 加密服务实现
   - CryptoUtils 加密工具
   - EncryptionService 加密服务
   - ZeroKnowledgeProofService 零知识证明

### 📋 配置

10. **[requirements.txt](requirements.txt)** - Python 依赖

---

## 📚 按用途查找

### 我想了解系统架构

→ 阅读 [CLOUD_ARCHITECTURE.md](CLOUD_ARCHITECTURE.md)

**关键章节：**
- 1. 架构概览
- 2. 核心服务模块
- 3. 数据存储架构
- 4. 实时同步流程

---

### 我想开发 API 客户端

→ 阅读 [OPENAPI_SPEC.md](OPENAPI_SPEC.md)

**关键章节：**
- 2. 同步操作 API
- 3. 冲突解决 API
- 4. 版本控制 API
- 5. 加密服务 API
- 6. WebSocket API

**示例请求：**
```bash
# 提交同步操作
curl -X POST http://localhost:8000/v1/sync/operations \
  -H "Content-Type: application/json" \
  -d '{...}'

# 获取同步状态
curl http://localhost:8000/v1/sync/status?client_id=client_1

# 加密数据
curl -X POST http://localhost:8000/v1/encryption/encrypt \
  -H "Content-Type: application/json" \
  -d '{"data": "..."}'
```

---

### 我想部署到生产环境

→ 阅读 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

**快速步骤：**
1. 选择部署方式 (Docker 或 Kubernetes)
2. 配置环境变量
3. 初始化数据库
4. 启动服务
5. 配置监控告警
6. 设置备份策略

**关键章节：**
- 2. Docker 部署
- 3. Kubernetes 部署
- 4. 监控与日志
- 5. 备份与恢复

---

### 我想理解冲突解决

→ 阅读 [CLOUD_ARCHITECTURE.md](CLOUD_ARCHITECTURE.md) 第5章

**关键概念：**
- 向量时钟 (Vector Clock)
- CRDT (Conflict-free RDT)
- 最后写入胜利 (LWW)
- 人工审核

**代码实现：**
→ 查看 [sync_service.py](sync_service.py) 中的 `ConflictResolver` 类

---

### 我想理解加密机制

→ 阅读 [CLOUD_ARCHITECTURE.md](CLOUD_ARCHITECTURE.md) 第6章

**关键概念：**
- 端到端加密
- RSA-4096 密钥交换
- AES-256-GCM 数据加密
- 零知识证明

**代码实现：**
→ 查看 [encryption_service.py](encryption_service.py)

---

### 我想设计数据库

→ 阅读 [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)

**关键表：**
- sync_operations - 同步操作
- version_snapshots - 版本快照
- conflict_records - 冲突记录
- sync_state - 同步状态
- encryption_keys - 加密密钥

**关键章节：**
- 1. 核心表设计
- 2. 关系表设计
- 3. 审计与日志表
- 4. 性能优化

---

### 我想集成到现有系统

→ 阅读 [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)

**快速步骤：**
1. 安装依赖 (requirements.txt)
2. 初始化数据库
3. 集成同步服务
4. 集成加密服务
5. 配置 WebSocket
6. 添加测试

**关键章节：**
- 2. 核心模块集成
- 3. 数据库初始化
- 4. 测试套件

---

### 我想监控系统性能

→ 阅读 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 第4章

**关键指标：**
- 同步操作吞吐量
- 冲突检测率
- 平均同步延迟
- 成功率
- 错误率

**监控工具：**
- Prometheus - 指标收集
- Grafana - 可视化
- ELK Stack - 日志分析

---

### 我想排查问题

→ 阅读 [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) 第7章

**常见问题：**
- 同步操作失败
- 高延迟
- 内存泄漏
- 数据库连接问题
- Redis 连接问题

---

## 🔍 按技术栈查找

### FastAPI

- [OPENAPI_SPEC.md](OPENAPI_SPEC.md) - API 设计
- [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) 第2章 - 集成示例

### PostgreSQL

- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - 完整 Schema
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 第3.3章 - K8s 部署

### Redis

- [CLOUD_ARCHITECTURE.md](CLOUD_ARCHITECTURE.md) 第3.2章 - 缓存设计
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 第3.4章 - K8s 部署

### Qdrant

- [CLOUD_ARCHITECTURE.md](CLOUD_ARCHITECTURE.md) 第3.3章 - 向量存储
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - 部署配置

### Docker

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 第2章 - Docker 部署
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 第2.2章 - Docker Compose

### Kubernetes

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 第3章 - K8s 部署
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 第3.6章 - Ingress 配置

### Prometheus & Grafana

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 第4.1章 - Prometheus 配置
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 第4.2章 - Grafana 仪表板

---

## 📊 文档统计

| 文档 | 行数 | 字数 | 主题 |
|------|------|------|------|
| README.md | 400+ | 8,000+ | 项目概览 |
| CLOUD_ARCHITECTURE.md | 600+ | 13,500+ | 架构设计 |
| OPENAPI_SPEC.md | 550+ | 12,000+ | API规范 |
| DATABASE_SCHEMA.md | 500+ | 10,000+ | 数据库设计 |
| DEPLOYMENT_GUIDE.md | 550+ | 12,000+ | 部署方案 |
| IMPLEMENTATION_GUIDE.md | 450+ | 10,000+ | 实现指南 |
| sync_service.py | 800+ | - | 同步服务 |
| encryption_service.py | 700+ | - | 加密服务 |
| DELIVERY_SUMMARY.md | 400+ | 8,000+ | 交付总结 |
| **总计** | **4,950+** | **73,500+** | - |

---

## 🎯 学习路径

### 初级 (了解系统)

1. 阅读 [README.md](README.md) - 5分钟
2. 阅读 [CLOUD_ARCHITECTURE.md](CLOUD_ARCHITECTURE.md) 第1-2章 - 15分钟
3. 查看 [OPENAPI_SPEC.md](OPENAPI_SPEC.md) 示例 - 10分钟

**总耗时：** 30分钟

### 中级 (理解设计)

1. 完整阅读 [CLOUD_ARCHITECTURE.md](CLOUD_ARCHITECTURE.md) - 30分钟
2. 完整阅读 [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - 20分钟
3. 阅读 [OPENAPI_SPEC.md](OPENAPI_SPEC.md) - 25分钟
4. 查看 [sync_service.py](sync_service.py) 代码 - 20分钟

**总耗时：** 95分钟

### 高级 (实现部署)

1. 完整阅读所有文档 - 2小时
2. 研究 [sync_service.py](sync_service.py) 和 [encryption_service.py](encryption_service.py) - 1小时
3. 按照 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 部署 - 1小时
4. 按照 [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) 集成 - 2小时

**总耗时：** 6小时

---

## 🔗 相关链接

### 项目资源

- GitHub: https://github.com/x-agent/x-agent
- 文档: https://docs.x-agent.io
- API文档: http://localhost:8000/docs

### 技术参考

- FastAPI: https://fastapi.tiangolo.com/
- PostgreSQL: https://www.postgresql.org/
- Redis: https://redis.io/
- Qdrant: https://qdrant.tech/
- Kubernetes: https://kubernetes.io/

### 概念参考

- Vector Clock: https://en.wikipedia.org/wiki/Vector_clock
- CRDT: https://crdt.tech/
- End-to-End Encryption: https://en.wikipedia.org/wiki/End-to-end_encryption
- Zero Knowledge Proof: https://en.wikipedia.org/wiki/Zero-knowledge_proof

---

## ❓ 常见问题

**Q: 从哪里开始？**
A: 从 [README.md](README.md) 开始，然后根据你的需求选择相应的文档。

**Q: 如何快速部署？**
A: 按照 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 第2章使用 Docker Compose。

**Q: 如何开发客户端？**
A: 参考 [OPENAPI_SPEC.md](OPENAPI_SPEC.md) 中的 API 规范和示例。

**Q: 如何理解冲突解决？**
A: 阅读 [CLOUD_ARCHITECTURE.md](CLOUD_ARCHITECTURE.md) 第5章和 [sync_service.py](sync_service.py) 中的代码。

**Q: 如何监控系统？**
A: 参考 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 第4章的监控配置。

---

## 📞 获取帮助

- 📖 查看文档
- 🐛 报告问题: https://github.com/x-agent/x-agent/issues
- 💬 讨论: https://github.com/x-agent/x-agent/discussions
- 📧 联系团队: team@x-agent.io

---

## ✅ 检查清单

在开始之前，确保你已经：

- [ ] 阅读了 [README.md](README.md)
- [ ] 理解了系统架构 ([CLOUD_ARCHITECTURE.md](CLOUD_ARCHITECTURE.md))
- [ ] 熟悉了 API 规范 ([OPENAPI_SPEC.md](OPENAPI_SPEC.md))
- [ ] 了解了数据库设计 ([DATABASE_SCHEMA.md](DATABASE_SCHEMA.md))
- [ ] 准备好部署环境 ([DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md))

---

**最后更新：** 2026-05-27  
**维护者：** X-Agent Team  
**许可证：** MIT
