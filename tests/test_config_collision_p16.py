"""P1-6a 回归护栏：``backend/app/core`` 下不得再出现与 ``config/`` 包同名的 ``config.py``。

背景（实测）：
``backend/app/core/config.py`` 与同名包 ``backend/app/core/config/`` 曾并存。
Python 的查找顺序是 **包优先于同名模块**，因此 ``import backend.app.core.config``
静默解析到 **包**，``config.py`` 完全不可达（零可达引用，且 ``core/__pycache__``
下从未生成过 ``config.cpython-*.pyc``）。

这类"同名并存"的危害不是报错，而是**静默**：任何以为在修改 ``config.py`` 的人，
实际生效的却是包 —— 改动被无声吞掉。该死模块已按仓库约定归档至
``archive/dead_code_2026-09-14/backend/app/core/config.py``（sha256
``a81cbf41704c7aa19708f0ad9eec3b3f42240f9333b9178a34d9b385d603a25a``）。

本护栏的作用：阻止同名模块被重新引入而不被察觉。
"""

from __future__ import annotations

from pathlib import Path

import backend.app.core.config as core_config


def test_core_config_resolves_to_package_not_shadowed_module() -> None:
    """``backend.app.core.config`` 必须解析为包，而不是被同名模块遮蔽。"""
    assert getattr(core_config, "__path__", None) is not None, (
        "backend.app.core.config 应解析为包（core/config/），"
        "实际却被同名模块遮蔽了 —— 说明 core/config.py 又被加了回来"
    )
    assert Path(core_config.__file__).name == "__init__.py"


def test_no_shadowing_config_module_alongside_the_package() -> None:
    """包同级目录下不得存在会遮蔽它的 config.py。"""
    core_dir = Path(core_config.__file__).resolve().parent.parent
    shadow = core_dir / "config.py"
    assert not shadow.exists(), (
        f"检测到与包同名的模块 {shadow} —— 它会静默遮蔽 core/config/ 包，"
        "使对 config.py 的修改完全失效。新增配置请放入 core/config/ 目录内。"
    )


def test_package_still_exports_the_live_settings_api() -> None:
    """归档死模块不得影响包对外提供的活 API（audit.py 依赖 get_settings）。"""
    for name in ("Settings", "get_settings"):
        assert hasattr(core_config, name), f"core.config 包不再导出 {name}"
