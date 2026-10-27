"""Initialize Railway-mounted volume safely, then drop root privileges.

Railway volumes mount over image filesystem permissions. This one-time bootstrap
keeps the Uvicorn process non-root while retaining persistent SQLite writes.
"""
from __future__ import annotations

import os
from pathlib import Path

UID = 10001
GID = 10001
root = Path("/data")
root.mkdir(parents=True, exist_ok=True)
if os.geteuid() == 0:
    os.chown(root, UID, GID)
    for entry in root.iterdir():
        if entry.is_file() and not entry.is_symlink():
            os.chown(entry, UID, GID)
    os.setgroups([])
    os.setgid(GID)
    os.setuid(UID)
if not os.access(root, os.W_OK):
    raise SystemExit("Railway volume /data is not writable as uid 10001")
os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])
