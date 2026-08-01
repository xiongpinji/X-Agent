"""TODO 应用包入口。

本模块作为 TODO 应用包的统一入口，负责导出核心组件，
方便外部通过 ``from todo_app import ...`` 的方式引用。

典型用法::

    from todo_app import TodoService, TodoRepository, Todo

    service = TodoService(TodoRepository())
    todo = service.create_todo("学习 Python", "学习类型注解和 dataclass")
"""

from todo_app.models import Todo, TodoFilter
from todo_app.repository import TodoRepository
from todo_app.service import TodoService

__all__ = [
    "Todo",
    "TodoFilter",
    "TodoRepository",
    "TodoService",
]

__version__ = "1.0.0"
