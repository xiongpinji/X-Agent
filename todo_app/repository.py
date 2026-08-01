"""TODO 数据访问层（内存存储）。

本模块实现 ``TodoRepository``，负责以内存字典的方式存储和检索
待办事项，提供基本的增删改查与列表/筛选能力。

典型用法::

    from todo_app.repository import TodoRepository

    repo = TodoRepository()
    repo.add(todo)
"""

from __future__ import annotations

from typing import List, Optional

from todo_app.models import Todo, TodoFilter


class TodoRepository:
    """基于内存字典的 TODO 仓库。

    使用 ``dict[int, Todo]`` 作为底层存储，以 ``id`` 作为键。
    """

    def __init__(self) -> None:
        """初始化一个空的仓库。"""
        self._storage: dict[int, Todo] = {}

    def add(self, todo: Todo) -> Todo:
        """新增一条待办事项。

        参数:
            todo: 待存储的待办事项。

        返回:
            存储后的待办事项。
        """
        self._storage[todo.id] = todo
        return todo

    def get(self, todo_id: int) -> Optional[Todo]:
        """根据 id 获取待办事项。

        参数:
            todo_id: 待办事项的唯一标识。

        返回:
            找到的待办事项，若不存在则返回 None。
        """
        return self._storage.get(todo_id)

    def update(self, todo: Todo) -> Optional[Todo]:
        """更新一条已存在的待办事项。

        参数:
            todo: 包含新数据的待办事项（id 用于定位）。

        返回:
            更新后的待办事项，若不存在则返回 None。
        """
        if todo.id not in self._storage:
            return None
        self._storage[todo.id] = todo
        return todo

    def delete(self, todo_id: int) -> bool:
        """删除指定 id 的待办事项。

        参数:
            todo_id: 待删除待办事项的唯一标识。

        返回:
            若删除成功返回 True，否则返回 False。
        """
        return self._storage.pop(todo_id, None) is not None

    def list_all(self) -> List[Todo]:
        """返回全部待办事项。

        返回:
            按 id 升序排列的待办事项列表。
        """
        return [self._storage[key] for key in sorted(self._storage)]

    def filter_by(self, filt: TodoFilter) -> List[Todo]:
        """根据筛选条件过滤待办事项。

        参数:
            filt: 筛选条件。

        返回:
            满足所有条件的待办事项列表。
        """
        result: List[Todo] = []
        for todo in self._storage.values():
            if filt.completed is not None and todo.completed != filt.completed:
                continue
            if filt.priority is not None and todo.priority != filt.priority:
                continue
            if filt.title is not None and filt.title.lower() not in todo.title.lower():
                continue
            if filt.tag is not None and filt.tag not in todo.tags:
                continue
            result.append(todo)
        return result
