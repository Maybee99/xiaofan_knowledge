"""Internal file-system utilities."""

import os
import tempfile
from pathlib import Path


def _strip_surrogates(text: str) -> str:
    """Remove unpaired surrogate code points (broken emoji) from text.

    Surrogates (U+D800–U+DFFF) are invalid in UTF-8 and would crash a utf-8
    file write. They can leak in from web-search results or AI responses.
    Removing them is safe — they never encode real text.
    """
    if not isinstance(text, str) or not any(
        0xD800 <= ord(ch) <= 0xDFFF for ch in text
    ):
        return text
    return "".join(ch for ch in text if not 0xD800 <= ord(ch) <= 0xDFFF)


def _atomic_write_text(path: Path, content: str) -> None:
    """Write text via a same-directory temporary file and atomic replacement."""
    content = _strip_surrogates(content)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
