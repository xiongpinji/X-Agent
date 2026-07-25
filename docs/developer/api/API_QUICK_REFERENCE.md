# X-Agent API 快速参考指南

## 快速开始

### 启动API服务器
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 访问API文档
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

---

## API端点速查表

### 流式输出 (Streaming)
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/agent/stream/{run_id}` | 流式输出代理执行 |
| POST | `/api/v1/agent/stream/subscribe` | 订阅流 |
| DELETE | `/api/v1/agent/stream/{run_id}` | 取消订阅 |
| GET | `/api/v1/agent/stream/status` | 获取流状态 |

### 任务管理 (Tasks)
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/tasks` | 列出所有任务 |
| POST | `/api/v1/tasks` | 创建新任务 |
| GET | `/api/v1/tasks/{task_id}` | 获取任务详情 |
| PUT | `/api/v1/tasks/{task_id}` | 更新任务 |
| DELETE | `/api/v1/tasks/{task_id}` | 删除任务 |
| POST | `/api/v1/tasks/{task_id}/complete` | 标记完成 |
| GET | `/api/v1/tasks/filter` | 过滤任务 |
| POST | `/api/v1/tasks/batch` | 批量操作 |

### 交互式问题 (Questions)
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/questions/ask` | 提出问题 |
| GET | `/api/v1/questions/{question_id}` | 获取问题详情 |
| POST | `/api/v1/questions/{question_id}/answer` | 提交答案 |
| GET | `/api/v1/questions/pending` | 获取待处理问题 |
| DELETE | `/api/v1/questions/{question_id}` | 关闭问题 |
| POST | `/api/v1/questions/batch` | 批量操作 |

### 文件预览 (File Preview)
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/files/preview/{file_id}` | 预览文件 |
| POST | `/api/v1/files/preview/generate` | 生成预览 |
| GET | `/api/v1/files/preview/formats` | 支持的格式 |
| POST | `/api/v1/files/preview/cache` | 缓存预览 |
| DELETE | `/api/v1/files/preview/{file_id}` | 清除缓存 |

### 并行代理 (Parallel Agents)
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/agents/parallel/spawn` | 启动并行代理 |
| GET | `/api/v1/agents/parallel/{batch_id}/status` | 获取状态 |
| GET | `/api/v1/agents/parallel/{batch_id}/results` | 获取结果 |
| POST | `/api/v1/agents/parallel/{batch_id}/cancel` | 取消批次 |
| GET | `/api/v1/agents/parallel/batches` | 列出批次 |
| POST | `/api/v1/agents/parallel/communicate` | 代理通信 |
| GET | `/api/v1/agents/parallel/{batch_id}/logs` | 获取日志 |

### 浏览器增强 (Browser Advanced)
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/browser/advanced/network` | 网络请求 |
| GET | `/api/v1/browser/advanced/performance` | 性能指标 |
| GET | `/api/v1/browser/advanced/console` | 控制台日志 |
| POST | `/api/v1/browser/advanced/record` | 开始录制 |
| POST | `/api/v1/browser/advanced/stop-record` | 停止录制 |
| GET | `/api/v1/browser/advanced/har` | 导出HAR |
| POST | `/api/v1/browser/advanced/screenshot` | 截图 |
| GET | `/api/v1/browser/advanced/dom` | DOM快照 |

### 工作区 (Workspace)
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/workspace/create` | 创建工作区 |
| GET | `/api/v1/workspace/{workspace_id}` | 获取信息 |
| DELETE | `/api/v1/workspace/{workspace_id}` | 删除工作区 |
| POST | `/api/v1/workspace/{workspace_id}/mount` | 挂载目录 |
| POST | `/api/v1/workspace/{workspace_id}/unmount` | 卸载目录 |
| GET | `/api/v1/workspace/{workspace_id}/files` | 列出文件 |
| POST | `/api/v1/workspace/{workspace_id}/upload` | 上传文件 |
| GET | `/api/v1/workspace/list` | 列出工作区 |

### 工具批量 (Tools Batch)
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/tools/batch/execute` | 执行批量工具 |
| GET | `/api/v1/tools/batch/{batch_id}/status` | 获取状态 |
| GET | `/api/v1/tools/batch/{batch_id}/results` | 获取结果 |
| POST | `/api/v1/tools/batch/{batch_id}/cancel` | 取消批次 |
| GET | `/api/v1/tools/batch/history` | 获取历史 |
| POST | `/api/v1/tools/batch/validate` | 验证请求 |

### 记忆增强 (Memory Enhanced)
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/memory/store` | 存储记忆 |
| GET | `/api/v1/memory/recall` | 回忆记忆 |
| GET | `/api/v1/memory/search` | 搜索记忆 |
| POST | `/api/v1/memory/relate` | 创建关系 |
| GET | `/api/v1/memory/related/{memory_id}` | 获取相关 |
| POST | `/api/v1/memory/merge` | 合并记忆 |
| GET | `/api/v1/memory/stats` | 获取统计 |
| DELETE | `/api/v1/memory/{memory_id}` | 删除记忆 |
| POST | `/api/v1/memory/export` | 导出记忆 |
| POST | `/api/v1/memory/import` | 导入记忆 |

---

## 常见请求示例

### 1. 创建任务
```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Task",
    "description": "Task description",
    "priority": "high"
  }'
```

### 2. 列出任务
```bash
curl -X GET "http://localhost:8000/api/v1/tasks?page=1&page_size=20" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. 启动并行代理
```bash
curl -X POST http://localhost:8000/api/v1/agents/parallel/spawn \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agents": [
      {"id": "agent-1", "task": "..."},
      {"id": "agent-2", "task": "..."}
    ],
    "isolation_mode": "process"
  }'
```

### 4. 存储记忆
```bash
curl -X POST http://localhost:8000/api/v1/memory/store \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Important information",
    "type": "fact",
    "importance": 0.8
  }'
```

### 5. 搜索记忆
```bash
curl -X GET "http://localhost:8000/api/v1/memory/search?query=important&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 认证

### Bearer Token
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/tasks
```

### API Key
```bash
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/api/v1/tasks
```

---

## 速率限制

| 端点 | 限制 |
|------|------|
| `/api/v1/auth/login` | 10次/分钟 |
| `/api/v1/auth/register` | 5次/分钟 |
| 其他API | 100次/分钟 |

响应头中包含：
- `X-RateLimit-Limit`: 限制数
- `X-RateLimit-Remaining`: 剩余次数
- `X-RateLimit-Reset`: 重置时间

---

## 错误处理

### 标准错误响应
```json
{
  "error": "error_code",
  "message": "Human-readable message",
  "details": {}
}
```

### 常见错误码
| 状态码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 403 | 禁止访问 |
| 404 | 资源不存在 |
| 429 | 超过速率限制 |
| 500 | 服务器错误 |

---

## 测试

### 运行API测试
```bash
python scripts/test_api_endpoints.py \
  --base-url http://localhost:8000 \
  --output api_test_report.json
```

### 查看测试报告
```bash
cat api_test_report.json | python -m json.tool
```

---

## 环境变量

### 必需
- `DATABASE_URL`: 数据库连接字符串
- `REDIS_URL`: Redis连接字符串

### 可选
- `CORS_ORIGINS`: CORS允许的源（逗号分隔）
- `REQUIRE_API_KEY`: 是否需要API密钥（true/false）
- `APP_MODE`: 应用模式（development/production）

---

## 文件位置

| 文件 | 位置 |
|------|------|
| 主应用 | `backend/app/main.py` |
| API模块 | `backend/app/api/` |
| 测试脚本 | `scripts/test_api_endpoints.py` |
| 完整文档 | `API_ENDPOINTS_DOCUMENTATION.md` |
| 注册总结 | `API_REGISTRATION_SUMMARY.md` |

---

## 常见问题

### Q: 如何获取API令牌？
A: 使用登录端点获取令牌：
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'
```

### Q: 如何处理超时？
A: 增加请求超时时间或检查服务器状态。

### Q: 如何调试API问题？
A: 查看服务器日志和API测试报告。

### Q: 支持哪些文件格式预览？
A: 查看 `/api/v1/files/preview/formats` 端点。

---

## 相关资源

- 完整API文档: `API_ENDPOINTS_DOCUMENTATION.md`
- 注册总结: `API_REGISTRATION_SUMMARY.md`
- 测试脚本: `scripts/test_api_endpoints.py`
- 源代码: `backend/app/main.py`

---

**最后更新:** 2026-05-27  
**版本:** 1.0.0
