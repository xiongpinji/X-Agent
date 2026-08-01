"""String utility helpers."""

import re


def slugify(text: str) -> str:
    """Convert text to a URL slug.

    Lowercases the input, replaces whitespace runs with a single hyphen,
    and strips out non-alphanumeric characters (excluding hyphens).

    Examples:
        >>> slugify('Hello World')
        'hello-world'
        >>> slugify('  Multiple   Spaces  ')
        'multiple-spaces'
        >>> slugify('Special!@#Chars')
        'specialchars'
        >>> slugify('')
        ''
        >>> slugify('already-slugged')
        'already-slugged'
    """
    if not isinstance(text, str):
        raise TypeError("slugify expects a string, got %r" % type(text).__name__)

    # Lowercase and collapse whitespace runs into a single space.
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)

    # Replace spaces with hyphens.
    text = text.replace(" ", "-")

    # Strip out any remaining non-alphanumeric characters except hyphens.
    text = re.sub(r"[^a-z0-9-]", "", text)

    return text
