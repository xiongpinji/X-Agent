"""TODO 数据模型定义。

本模块定义 TODO 应用所使用的基础数据模型，包括待办事项
``Todo`` 以及用于筛选待办事项的 ``TodoFilter``。

典型用法::

    from todo_app.models import Todo, TodoFilter

    todo = Todo(id=1, title="写报告", description="季度报告")
    filt = TodoFilter(completed=False)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Todo:
    """表示一条待办事项。

    属性:
        id: 唯一标识符。
        title: 标题。
        description: 详细描述。
        completed: 是否已完成，默认为 False。
        priority: 优先级，数值越大优先级越高，默认为 1。
        created_at: 创建时间（ISO 格式字符串）。
        tags: 标签列表，默认为空列表。
    """

    id: int
    title: str
    description: str
    completed: bool = False
    priority: int = 1
    created_at: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class TodoFilter:
    """描述待办事项的筛选条件。

    所有字段均为可选；为 None 的字段表示不进行该维度的过滤。

    属性:
        completed: 按完成状态过滤。
        priority: 按优先级过滤。
        title: 按标题包含匹配过滤。
        tag: 按标签包含匹配过滤。
    """

    completed: Optional[bool] = None
    priority: Optional[int] = None
    title: Optional[str] = None
    tag: Optional[str] = None
