"""Utility helper functions."""


def calculate_average(numbers: list[float]) -> float:
    """计算一组数字的平均值。

    Args:
        numbers: 数字列表。

    Returns:
        列表中所有数字的平均值；如果列表为空，则返回 0.0。
    """
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)
