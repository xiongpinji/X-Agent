"""Hello world module."""


def hello_world() -> str:
    """Return the classic greeting string.

    Returns:
        str: The greeting "Hello, World!".
    """
    return "Hello, World!"


def main() -> None:
    """Print the greeting to stdout when run as a script."""
    print(hello_world())


if __name__ == "__main__":
    main()
