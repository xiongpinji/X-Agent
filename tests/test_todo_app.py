"""TODO 应用单元测试。

使用 pytest 编写，覆盖 TodoService 的 CRUD、搜索与统计功能。
运行方式::

    pytest tests/test_todo_app.py -v
"""

from __future__ import annotations

import pytest

from todo_app.models import Todo, TodoFilter
from todo_app.repository import TodoRepository
from todo_app.service import TodoService


@pytest.fixture
def service() -> TodoService:
    """提供一个新的 TodoService 实例。"""
    return TodoService()


def test_create_todo(service: TodoService) -> None:
    """测试创建待办事项。"""
    todo = service.create_todo(title="写报告", description="季度报告")
    assert todo.id == 1
    assert todo.title == "写报告"
    assert todo.completed is False
    assert todo.priority == 1
    assert todo.created_at != ""
    assert todo.tags == []


def test_get_todo(service: TodoService) -> None:
    """测试按 id 获取待办事项。"""
    created = service.create_todo(title="学习")
    fetched = service.get_todo(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "学习"


def test_get_todo_not_found(service: TodoService) -> None:
    """测试获取不存在的待办事项返回 None。"""
    assert service.get_todo(999) is None


def test_update_todo(service: TodoService) -> None:
    """测试更新待办事项字段。"""
    created = service.create_todo(title="旧标题")
    updated = service.update_todo(created.id, title="新标题", completed=True)
    assert updated is not None
    assert updated.title == "新标题"
    assert updated.completed is True


def test_update_todo_not_found(service: TodoService) -> None:
    """测试更新不存在的待办事项返回 None。"""
    assert service.update_todo(123, title="x") is None


def test_delete_todo(service: TodoService) -> None:
    """测试删除待办事项。"""
    created = service.create_todo(title="待删除")
    assert service.delete_todo(created.id) is True
    assert service.get_todo(created.id) is None
    assert service.delete_todo(created.id) is False


def test_list_todos(service: TodoService) -> None:
    """测试列出全部待办事项。"""
    service.create_todo(title="任务一")
    service.create_todo(title="任务二")
    todos = service.list_todos()
    assert len(todos) == 2


def test_search_todos(service: TodoService) -> None:
    """测试按标题模糊搜索。"""
    service.create_todo(title="学习 Python")
    service.create_todo(title="学习 Go")
    service.create_todo(title="写周报")
    results = service.search_todos("学习")
    assert len(results) == 2
    results = service.search_todos("python")
    assert len(results) == 1


def test_search_todos_empty(service: TodoService) -> None:
    """测试空关键字返回全部。"""
    service.create_todo(title="任务")
    assert len(service.search_todos("")) == 1


def test_get_stats(service: TodoService) -> None:
    """测试统计计数。"""
    service.create_todo(title="已完成")
    service.create_todo(title="待办一")
    service.create_todo(title="待办二")
    service.update_todo(1, completed=True)
    stats = service.get_stats()
    assert stats["total"] == 3
    assert stats["completed"] == 1
    assert stats["pending"] == 2


def test_repository_filter_by() -> None:
    """测试仓库层的筛选能力。"""
    repo = TodoRepository()
    repo.add(Todo(id=1, title="A", completed=False, priority=2, tags=["urgent"]))
    repo.add(Todo(id=2, title="B", completed=True, priority=1, tags=["normal"]))
    filt = TodoFilter(completed=False)
    assert len(repo.filter_by(filt)) == 1
    filt = TodoFilter(priority=1)
    assert len(repo.filter_by(filt)) == 1
    filt = TodoFilter(tag="urgent")
    assert len(repo.filter_by(filt)) == 1
