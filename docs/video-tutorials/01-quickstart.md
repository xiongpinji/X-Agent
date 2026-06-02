# 视频教程 1: X-Agent 快速入门 (5-7分钟)

**视频标题**: X-Agent 快速入门 - 5分钟创建你的第一个Agent

**目标受众**: 初学者、新用户

**学习成果**:
- 安装和配置 X-Agent
- 创建第一个 Agent
- 执行第一个任务
- 理解基本概念

---

## 脚本

### [00:00-00:20] 开场

```
欢迎来到 X-Agent 教程！

在这个视频中，我们将在 5 分钟内创建你的第一个 AI Agent。
无论你是开发者还是非技术用户，都能轻松上手。

让我们开始吧！
```

**视觉**: 
- X-Agent Logo 动画
- 项目主页截图
- 快速入门流程图

---

### [00:20-01:00] 安装 X-Agent

```
首先，让我们安装 X-Agent。

打开你的终端或命令行，运行以下命令：

git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core

然后创建虚拟环境：

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

最后安装依赖：

pip install -e ".[dev]"

安装通常需要 2-3 分钟。
```

**视觉**:
- 终端录屏
- 命令逐行显示
- 进度条动画
- 成功提示

---

### [01:00-01:40] 配置环境

```
接下来，我们需要配置环境变量。

复制示例配置文件：

cp .env.example .env

然后编辑 .env 文件，添加你的 API 密钥。

你需要：
1. OpenAI API 密钥（或其他 LLM 提供商）
2. 数据库连接信息（可选，使用默认值）
3. 其他服务配置（可选）

编辑完成后保存文件。
```

**视觉**:
- 文件浏览器截图
- .env 文件编辑演示
- 配置项说明

---

### [01:40-02:30] 启动服务

```
现在让我们启动 X-Agent 服务。

运行以下命令：

uvicorn backend.app.main:app --reload --port 8000

你会看到服务启动的日志。

打开浏览器，访问：

http://localhost:8000/docs

你会看到 API 文档和交互式界面。
```

**视觉**:
- 终端启动日志
- 浏览器打开 API 文档
- 交互式 API 界面演示

---

### [02:30-04:00] 创建第一个 Agent

```
现在让我们创建第一个 Agent。

创建一个新文件 my_first_agent.py：

import asyncio
from backend.app.core.agent import Agent
from backend.app.core.llm import LLMRouter

async def main():
    # 初始化 LLM 路由器
    llm_router = LLMRouter()
    
    # 创建 Agent
    agent = Agent(
        name="MyFirstAgent",
        description="我的第一个 Agent",
        llm_router=llm_router,
        system_prompt="你是一个有帮助的助手。"
    )
    
    # 执行任务
    result = await agent.execute(
        task="请告诉我今天的日期和时间"
    )
    
    print(f"Agent 响应: {result.output}")

# 运行
asyncio.run(main())

这个代码做了什么：
1. 导入必要的模块
2. 初始化 LLM 路由器
3. 创建一个 Agent
4. 执行一个简单的任务
5. 打印结果
```

**视觉**:
- 代码编辑器截图
- 代码逐行高亮
- 代码注释说明

---

### [04:00-04:45] 运行 Agent

```
现在让我们运行这个 Agent。

在终端中运行：

python my_first_agent.py

你会看到 Agent 的响应。

恭喜！你已经创建并运行了你的第一个 Agent！

Agent 做了什么：
1. 接收了你的任务
2. 使用 LLM 理解任务
3. 生成了响应
4. 返回了结果
```

**视觉**:
- 终端执行脚本
- 输出结果显示
- 成功提示

---

### [04:45-05:30] 下一步

```
现在你已经掌握了基础知识。

接下来你可以：

1. 添加工具
   - 让 Agent 可以调用外部服务
   - 执行更复杂的任务

2. 创建工作流
   - 定义多步骤的任务流程
   - 实现条件分支和并行执行

3. 使用记忆系统
   - 让 Agent 记住信息
   - 改进决策能力

4. 多 Agent 协作
   - 让多个 Agent 一起工作
   - 解决更复杂的问题

在下一个视频中，我们将深入探索这些高级功能。
```

**视觉**:
- 功能卡片展示
- 链接到下一个视频
- 文档链接

---

### [05:30-05:45] 总结和资源

```
总结一下我们学到的内容：

✓ 安装 X-Agent
✓ 配置环境
✓ 创建第一个 Agent
✓ 执行任务

更多资源：
- 完整文档: https://docs.x-agent.dev
- GitHub: https://github.com/x-agent/x-agent-core
- 社区论坛: https://community.x-agent.dev

感谢观看！
```

**视觉**:
- 学习成果检查清单
- 资源链接
- 订阅提示
- 下一个视频预告

---

## 截图和演示要点

### 关键截图
1. X-Agent 项目主页
2. 终端安装过程
3. .env 配置文件
4. API 文档界面
5. 代码编辑器
6. 执行结果

### 演示要点
- 清晰的语音讲解
- 适当的停顿和强调
- 代码高亮和注释
- 实时执行演示
- 成功反馈

---

## 制作建议

### 录制设置
- 分辨率: 1920x1080 (1080p)
- 帧率: 30fps
- 音频: 44.1kHz, 立体声
- 麦克风: 清晰的语音，无背景噪音

### 编辑建议
- 添加中英文字幕
- 代码部分放大显示
- 添加背景音乐（低音量）
- 添加过渡效果
- 添加吸引人的缩略图

### 字幕内容
- 中文: 清晰的普通话
- 英文: 准确的技术术语翻译

---

## 常见问题

**Q: 我没有 OpenAI API 密钥怎么办？**
A: 你可以使用其他 LLM 提供商，如 Claude、Gemini 等。X-Agent 支持多个提供商。

**Q: 安装失败怎么办？**
A: 检查 Python 版本（需要 3.11+）和网络连接。查看文档中的故障排除部分。

**Q: 我可以在 Windows 上运行吗？**
A: 可以。只需在激活虚拟环境时使用 `venv\Scripts\activate`。

---

## 下一个视频预告

在下一个视频中，我们将学习：
- 如何为 Agent 添加工具
- 如何使用记忆系统
- 如何实现多 Agent 协作

敬请期待！
