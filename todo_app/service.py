"""TODO 业务逻辑层。

本模块实现 ``TodoService``，封装底层仓库，对外提供业务层面的
创建、查询、更新、删除、搜索与统计能力。

典型用法::

    from todo_app.service import TodoService

    service = TodoService()
    todo = service.create_todo(title="学习 Python")
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from todo_app.models import Todo, TodoFilter
from todo_app.repository import TodoRepository


class TodoService:
    """TODO 应用的服务层。

    负责管理待办事项的业务流程，并依赖 ``TodoRepository`` 完成持久化。
    """

    def __init__(self, repository: Optional[TodoRepository] = None) -> None:
        """初始化服务。

        参数:
            repository: 数据仓库，缺省时创建新的内存仓库。
        """
        self._repository = repository if repository is not None else TodoRepository()
        self._next_id: int = 1

    def create_todo(
        self,
        title: str,
        description: str = "",
        priority: int = 1,
        tags: Optional[List[str]] = None,
    ) -> Todo:
        """创建一条新的待办事项。

        参数:
            title: 标题。
            description: 描述。
            priority: 优先级。
            tags: 标签列表。

        返回:
            创建的待办事项。
        """
        todo = Todo(
            id=self._next_id,
            title=title,
            description=description,
            priority=priority,
            created_at=datetime.now().isoformat(),
            tags=list(tags) if tags else [],
        )
        self._next_id += 1
        return self._repository.add(todo)

    def get_todo(self, todo_id: int) -> Optional[Todo]:
        """根据 id 获取待办事项。

        参数:
            todo_id: 待办事项唯一标识。

        返回:
            找到的待办事项，不存在返回 None。
        """
        return self._repository.get(todo_id)

    def update_todo(
        self,
        todo_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        completed: Optional[bool] = None,
        priority: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Todo]:
        """更新指定 id 的待办事项字段。

        参数:
            todo_id: 待办事项唯一标识。
            title: 新的标题。
            description: 新的描述。
            completed: 新的完成状态。
            priority: 新的优先级。
            tags: 新的标签列表。

        返回:
            更新后的待办事项，若不存在返回 None。
        """
        existing = self._repository.get(todo_id)
        if existing is None:
            return None
        if title is not None:
            existing.title = title
        if description is not None:
            existing.description = description
        if completed is not None:
            existing.completed = completed
        if priority is not None:
            existing.priority = priority
        if tags is not None:
            existing.tags = list(tags)
        return self._repository.update(existing)

    def delete_todo(self, todo_id: int) -> bool:
        """删除指定 id 的待办事项。

        参数:
            todo_id: 待办事项唯一标识。

        返回:
            删除成功返回 True，否则返回 False。
        """
        return self._repository.delete(todo_id)

    def list_todos(self) -> List[Todo]:
        """返回全部待办事项。

        返回:
            待办事项列表。
        """
        return self._repository.list_all()

    def search_todos(self, keyword: str) -> List[Todo]:
        """按标题模糊匹配搜索待办事项。

        参数:
            keyword: 搜索关键字（大小写不敏感）。

        返回:
            标题包含关键字的待办事项列表。
        """
        if not keyword:
            return self.list_todos()
        filt = TodoFilter(title=keyword)
        return self._repository.filter_by(filt)

    def get_stats(self) -> Dict[str, int]:
        """统计待办事项数量。

        返回:
            包含 total / completed / pending 三组计数的字典。
        """
        all_todos = self.list_todos()
        completed = sum(1 for todo in all_todos if todo.completed)
        return {
            "total": len(all_todos),
            "completed": completed,
            "pending": len(all_todos) - completed,
        }
