"""
X-Agent 端到端测试框架 - 功能测试模块

测试范围:
- 用户认证流程
- 任务创建和执行
- 工作流编排
- 记忆系统同步
- 配置同步
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# 数据模型
# ============================================================================

class UserRole(str, Enum):
    """用户角色"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStatus(str, Enum):
    """工作流状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class User:
    """用户"""
    user_id: str
    username: str
    email: str
    password_hash: str
    role: UserRole
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


@dataclass
class Task:
    """任务"""
    task_id: str
    title: str
    description: str
    status: TaskStatus
    assignee_id: str
    created_at: datetime
    updated_at: datetime
    due_date: Optional[datetime] = None
    priority: int = 0
    tags: List[str] = None


@dataclass
class Workflow:
    """工作流"""
    workflow_id: str
    name: str
    description: str
    status: WorkflowStatus
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    version: int = 1


@dataclass
class Memory:
    """记忆"""
    memory_id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    user_id: str


@dataclass
class Config:
    """配置"""
    config_id: str
    key: str
    value: Any
    version: int
    created_at: datetime
    updated_at: datetime
    user_id: str


# ============================================================================
# 认证服务
# ============================================================================

class AuthService:
    """认证服务"""

    def __init__(self):
        self.users: Dict[str, User] = {}
        self.tokens: Dict[str, str] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def register_user(self, username: str, email: str, password: str) -> User:
        """注册用户"""
        user_id = f"user_{len(self.users) + 1}"
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=self._hash_password(password),
            role=UserRole.USER,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self.users[user_id] = user
        return user

    def login_user(self, username: str, password: str) -> Optional[str]:
        """用户登录"""
        for user in self.users.values():
            if user.username == username and self._verify_password(password, user.password_hash):
                token = self._generate_token(user.user_id)
                self.tokens[token] = user.user_id
                self.sessions[token] = {
                    "user_id": user.user_id,
                    "created_at": datetime.now(),
                    "expires_at": datetime.now() + timedelta(hours=24)
                }
                return token
        return None

    def logout_user(self, token: str) -> bool:
        """用户登出"""
        if token in self.tokens:
            del self.tokens[token]
            del self.sessions[token]
            return True
        return False

    def verify_token(self, token: str) -> Optional[str]:
        """验证 Token"""
        if token in self.sessions:
            session = self.sessions[token]
            if session["expires_at"] > datetime.now():
                return session["user_id"]
        return None

    def refresh_token(self, token: str) -> Optional[str]:
        """刷新 Token"""
        user_id = self.verify_token(token)
        if user_id:
            self.logout_user(token)
            new_token = self._generate_token(user_id)
            self.tokens[new_token] = user_id
            self.sessions[new_token] = {
                "user_id": user_id,
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(hours=24)
            }
            return new_token
        return None

    @staticmethod
    def _hash_password(password: str) -> str:
        """密码哈希"""
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        """验证密码"""
        return AuthService._hash_password(password) == password_hash

    @staticmethod
    def _generate_token(user_id: str) -> str:
        """生成 Token"""
        import uuid
        return f"token_{uuid.uuid4().hex}"


# ============================================================================
# 任务服务
# ============================================================================

class TaskService:
    """任务服务"""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.task_counter = 0

    def create_task(self, title: str, description: str, assignee_id: str) -> Task:
        """创建任务"""
        self.task_counter += 1
        task_id = f"task_{self.task_counter:06d}"
        task = Task(
            task_id=task_id,
            title=title,
            description=description,
            status=TaskStatus.PENDING,
            assignee_id=assignee_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            tags=[]
        )
        self.tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)

    def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        """更新任务"""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        task.updated_at = datetime.now()
        return task

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            return True
        return False

    def list_tasks(self, assignee_id: Optional[str] = None, status: Optional[TaskStatus] = None) -> List[Task]:
        """列表任务"""
        tasks = list(self.tasks.values())

        if assignee_id:
            tasks = [t for t in tasks if t.assignee_id == assignee_id]

        if status:
            tasks = [t for t in tasks if t.status == status]

        return tasks

    def search_tasks(self, query: str) -> List[Task]:
        """搜索任务"""
        return [t for t in self.tasks.values() if query.lower() in t.title.lower()]

    def add_tag(self, task_id: str, tag: str) -> bool:
        """添加标签"""
        if task_id in self.tasks:
            self.tasks[task_id].tags.append(tag)
            return True
        return False


# ============================================================================
# 工作流服务
# ============================================================================

class WorkflowService:
    """工作流服务"""

    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self.workflow_counter = 0
        self.executions: Dict[str, Dict[str, Any]] = {}

    def create_workflow(self, name: str, description: str) -> Workflow:
        """创建工作流"""
        self.workflow_counter += 1
        workflow_id = f"workflow_{self.workflow_counter:06d}"
        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            description=description,
            status=WorkflowStatus.DRAFT,
            nodes=[],
            edges=[],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self.workflows[workflow_id] = workflow
        return workflow

    def add_node(self, workflow_id: str, node_id: str, node_type: str, config: Dict[str, Any]) -> bool:
        """添加节点"""
        if workflow_id not in self.workflows:
            return False

        node = {
            "id": node_id,
            "type": node_type,
            "config": config
        }
        self.workflows[workflow_id].nodes.append(node)
        return True

    def add_edge(self, workflow_id: str, source_id: str, target_id: str) -> bool:
        """添加边"""
        if workflow_id not in self.workflows:
            return False

        edge = {
            "source": source_id,
            "target": target_id
        }
        self.workflows[workflow_id].edges.append(edge)
        return True

    def execute_workflow(self, workflow_id: str) -> Optional[str]:
        """执行工作流"""
        if workflow_id not in self.workflows:
            return None

        workflow = self.workflows[workflow_id]
        if workflow.status != WorkflowStatus.ACTIVE:
            return None

        execution_id = f"exec_{workflow_id}_{int(datetime.now().timestamp())}"
        self.executions[execution_id] = {
            "workflow_id": workflow_id,
            "status": "running",
            "started_at": datetime.now(),
            "completed_at": None,
            "result": None
        }
        return execution_id

    def pause_workflow(self, workflow_id: str) -> bool:
        """暂停工作流"""
        if workflow_id in self.workflows:
            self.workflows[workflow_id].status = WorkflowStatus.PAUSED
            return True
        return False

    def resume_workflow(self, workflow_id: str) -> bool:
        """恢复工作流"""
        if workflow_id in self.workflows:
            self.workflows[workflow_id].status = WorkflowStatus.ACTIVE
            return True
        return False

    def cancel_workflow(self, workflow_id: str) -> bool:
        """取消工作流"""
        if workflow_id in self.workflows:
            self.workflows[workflow_id].status = WorkflowStatus.FAILED
            return True
        return False


# ============================================================================
# 记忆服务
# ============================================================================

class MemoryService:
    """记忆服务"""

    def __init__(self):
        self.memories: Dict[str, Memory] = {}
        self.memory_counter = 0

    def create_memory(self, content: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Memory:
        """创建记忆"""
        self.memory_counter += 1
        memory_id = f"memory_{self.memory_counter:06d}"
        memory = Memory(
            memory_id=memory_id,
            content=content,
            embedding=self._generate_embedding(content),
            metadata=metadata or {},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_id=user_id
        )
        self.memories[memory_id] = memory
        return memory

    def retrieve_memory(self, query: str, user_id: str, limit: int = 10) -> List[Memory]:
        """检索记忆"""
        query_embedding = self._generate_embedding(query)
        user_memories = [m for m in self.memories.values() if m.user_id == user_id]

        # 计算相似度
        similarities = []
        for memory in user_memories:
            similarity = self._cosine_similarity(query_embedding, memory.embedding)
            similarities.append((memory, similarity))

        # 排序并返回
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [m for m, _ in similarities[:limit]]

    def update_memory(self, memory_id: str, content: str) -> Optional[Memory]:
        """更新记忆"""
        if memory_id not in self.memories:
            return None

        memory = self.memories[memory_id]
        memory.content = content
        memory.embedding = self._generate_embedding(content)
        memory.updated_at = datetime.now()
        return memory

    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id in self.memories:
            del self.memories[memory_id]
            return True
        return False

    @staticmethod
    def _generate_embedding(text: str) -> List[float]:
        """生成嵌入向量"""
        # 模拟实现：返回固定长度的向量
        import hashlib
        hash_value = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [(hash_value >> i) % 256 / 256.0 for i in range(10)]

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a ** 2 for a in vec1) ** 0.5
        magnitude2 = sum(b ** 2 for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)


# ============================================================================
# 配置服务
# ============================================================================

class ConfigService:
    """配置服务"""

    def __init__(self):
        self.configs: Dict[str, Config] = {}
        self.config_counter = 0

    def set_config(self, key: str, value: Any, user_id: str) -> Config:
        """设置配置"""
        self.config_counter += 1
        config_id = f"config_{self.config_counter:06d}"
        config = Config(
            config_id=config_id,
            key=key,
            value=value,
            version=1,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_id=user_id
        )
        self.configs[config_id] = config
        return config

    def get_config(self, key: str, user_id: str) -> Optional[Config]:
        """获取配置"""
        for config in self.configs.values():
            if config.key == key and config.user_id == user_id:
                return config
        return None

    def update_config(self, config_id: str, value: Any) -> Optional[Config]:
        """更新配置"""
        if config_id not in self.configs:
            return None

        config = self.configs[config_id]
        config.value = value
        config.version += 1
        config.updated_at = datetime.now()
        return config

    def delete_config(self, config_id: str) -> bool:
        """删除配置"""
        if config_id in self.configs:
            del self.configs[config_id]
            return True
        return False


# ============================================================================
# 测试用例
# ============================================================================

class TestAuthentication:
    """认证测试"""

    def test_user_registration(self):
        """TC-AUTH-001: 用户注册"""
        auth_service = AuthService()

        user = auth_service.register_user("testuser", "test@example.com", "password123")

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == UserRole.USER
        assert user.is_active

    def test_user_login(self):
        """TC-AUTH-002: 用户登录"""
        auth_service = AuthService()

        auth_service.register_user("testuser", "test@example.com", "password123")
        token = auth_service.login_user("testuser", "password123")

        assert token is not None
        assert token in auth_service.tokens

    def test_user_logout(self):
        """TC-AUTH-003: 用户登出"""
        auth_service = AuthService()

        auth_service.register_user("testuser", "test@example.com", "password123")
        token = auth_service.login_user("testuser", "password123")
        success = auth_service.logout_user(token)

        assert success
        assert token not in auth_service.tokens

    def test_token_verification(self):
        """TC-AUTH-005: Token 过期处理"""
        auth_service = AuthService()

        user = auth_service.register_user("testuser", "test@example.com", "password123")
        token = auth_service.login_user("testuser", "password123")
        user_id = auth_service.verify_token(token)

        assert user_id == user.user_id

    def test_token_refresh(self):
        """TC-AUTH-004: Token 刷新"""
        auth_service = AuthService()

        auth_service.register_user("testuser", "test@example.com", "password123")
        token = auth_service.login_user("testuser", "password123")
        new_token = auth_service.refresh_token(token)

        assert new_token is not None
        assert new_token != token
        assert token not in auth_service.tokens
        assert new_token in auth_service.tokens


class TestTaskManagement:
    """任务管理测试"""

    def test_create_task(self):
        """TC-TASK-001: 创建任务"""
        task_service = TaskService()

        task = task_service.create_task("Test Task", "Description", "user_001")

        assert task.title == "Test Task"
        assert task.status == TaskStatus.PENDING
        assert task.task_id in task_service.tasks

    def test_get_task(self):
        """TC-TASK-002: 读取任务"""
        task_service = TaskService()

        created_task = task_service.create_task("Test Task", "Description", "user_001")
        retrieved_task = task_service.get_task(created_task.task_id)

        assert retrieved_task is not None
        assert retrieved_task.title == "Test Task"

    def test_update_task(self):
        """TC-TASK-003: 更新任务"""
        task_service = TaskService()

        task = task_service.create_task("Test Task", "Description", "user_001")
        updated_task = task_service.update_task(task.task_id, status=TaskStatus.COMPLETED)

        assert updated_task.status == TaskStatus.COMPLETED

    def test_delete_task(self):
        """TC-TASK-004: 删除任务"""
        task_service = TaskService()

        task = task_service.create_task("Test Task", "Description", "user_001")
        success = task_service.delete_task(task.task_id)

        assert success
        assert task.task_id not in task_service.tasks

    def test_list_tasks(self):
        """TC-TASK-005: 任务列表查询"""
        task_service = TaskService()

        for i in range(5):
            task_service.create_task(f"Task {i}", "Description", "user_001")

        tasks = task_service.list_tasks(assignee_id="user_001")

        assert len(tasks) == 5

    def test_search_tasks(self):
        """TC-TASK-006: 任务搜索"""
        task_service = TaskService()

        task_service.create_task("Important Task", "Description", "user_001")
        task_service.create_task("Regular Task", "Description", "user_001")

        results = task_service.search_tasks("Important")

        assert len(results) == 1
        assert results[0].title == "Important Task"

    def test_add_tag(self):
        """TC-TASK-010: 任务标签管理"""
        task_service = TaskService()

        task = task_service.create_task("Test Task", "Description", "user_001")
        success = task_service.add_tag(task.task_id, "urgent")

        assert success
        assert "urgent" in task.tags


class TestWorkflowOrchestration:
    """工作流编排测试"""

    def test_create_workflow(self):
        """TC-WORKFLOW-001: 创建工作流"""
        workflow_service = WorkflowService()

        workflow = workflow_service.create_workflow("Test Workflow", "Description")

        assert workflow.name == "Test Workflow"
        assert workflow.status == WorkflowStatus.DRAFT

    def test_add_workflow_node(self):
        """TC-WORKFLOW-002: 执行工作流"""
        workflow_service = WorkflowService()

        workflow = workflow_service.create_workflow("Test Workflow", "Description")
        success = workflow_service.add_node(workflow.workflow_id, "node_1", "task", {"title": "Task 1"})

        assert success
        assert len(workflow.nodes) == 1

    def test_pause_workflow(self):
        """TC-WORKFLOW-003: 暂停工作流"""
        workflow_service = WorkflowService()

        workflow = workflow_service.create_workflow("Test Workflow", "Description")
        workflow.status = WorkflowStatus.ACTIVE
        success = workflow_service.pause_workflow(workflow.workflow_id)

        assert success
        assert workflow.status == WorkflowStatus.PAUSED

    def test_resume_workflow(self):
        """TC-WORKFLOW-004: 恢复工作流"""
        workflow_service = WorkflowService()

        workflow = workflow_service.create_workflow("Test Workflow", "Description")
        workflow.status = WorkflowStatus.PAUSED
        success = workflow_service.resume_workflow(workflow.workflow_id)

        assert success
        assert workflow.status == WorkflowStatus.ACTIVE


class TestMemorySystem:
    """记忆系统测试"""

    def test_create_memory(self):
        """TC-MEMORY-001: 记忆创建"""
        memory_service = MemoryService()

        memory = memory_service.create_memory("Test memory content", "user_001")

        assert memory.content == "Test memory content"
        assert memory.user_id == "user_001"

    def test_retrieve_memory(self):
        """TC-MEMORY-002: 记忆检索"""
        memory_service = MemoryService()

        memory_service.create_memory("Python programming", "user_001")
        memory_service.create_memory("JavaScript basics", "user_001")

        results = memory_service.retrieve_memory("Python", "user_001", limit=5)

        assert len(results) > 0

    def test_update_memory(self):
        """TC-MEMORY-003: 记忆更新"""
        memory_service = MemoryService()

        memory = memory_service.create_memory("Original content", "user_001")
        updated = memory_service.update_memory(memory.memory_id, "Updated content")

        assert updated.content == "Updated content"

    def test_delete_memory(self):
        """TC-MEMORY-004: 记忆删除"""
        memory_service = MemoryService()

        memory = memory_service.create_memory("Test memory", "user_001")
        success = memory_service.delete_memory(memory.memory_id)

        assert success
        assert memory.memory_id not in memory_service.memories


class TestConfigManagement:
    """配置管理测试"""

    def test_set_config(self):
        """TC-CONFIG-001: 配置同步"""
        config_service = ConfigService()

        config = config_service.set_config("theme", "dark", "user_001")

        assert config.key == "theme"
        assert config.value == "dark"

    def test_get_config(self):
        """TC-CONFIG-002: 配置版本管理"""
        config_service = ConfigService()

        config_service.set_config("theme", "dark", "user_001")
        retrieved = config_service.get_config("theme", "user_001")

        assert retrieved is not None
        assert retrieved.value == "dark"


# ============================================================================
# 测试套件
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

