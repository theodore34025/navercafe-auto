"""Owner-only, atomic storage for Playwright authentication state."""
import json
import os
import tempfile
from pathlib import Path


def save_state(path: Path, state: dict):
    path = Path(path).absolute()
    fd, temporary = tempfile.mkstemp(prefix='.session-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(state, stream, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
