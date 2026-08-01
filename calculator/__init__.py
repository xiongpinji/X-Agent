"""Calculator package entry point.

This package provides a simple calculator with arithmetic operations
and a history tracking feature.
"""

from .core import Calculator
from .history import History

__all__ = ["Calculator", "History"]
__version__ = "1.0.0"
