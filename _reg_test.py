from _reg_mod import multiply, divide


def test_multiply():
    assert multiply(2, 3) == 6


def test_multiply_negative():
    assert multiply(-2, 3) == -6


def test_divide():
    assert divide(10, 2) == 5


def test_divide_zero():
    assert divide(5, 2) == 2.5
