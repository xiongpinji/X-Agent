"""String utility functions."""

import re


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug.

    Lowercases the text, replaces runs of whitespace with a single hyphen,
    and strips non-alphanumeric characters.
    """
    text = text.lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9-]", "", text)
    return text
