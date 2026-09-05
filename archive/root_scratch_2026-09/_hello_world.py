"""Hello world module.

Provides a simple function that returns the classic "Hello, World!" greeting.
"""


def hello_world() -> str:
    """Return the classic "Hello, World!" greeting string.

    Returns:
        str: The greeting message.
    """
    return "Hello, World!"


if __name__ == "__main__":
    print(hello_world())
