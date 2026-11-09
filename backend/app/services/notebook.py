"""Python execution for notebook cells, in a separate process with limits.

This is resource-limited isolation, not a security sandbox. It runs user code as
the backend user with the backend's filesystem access, which is appropriate when
BioIDE runs on the user's own machine and is stated plainly in the API response.
A hosted deployment must put this behind a container or gVisor boundary.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
from pathlib import Path

from ..config import settings
from ..store import store

PREAMBLE = textwrap.dedent("""
    import resource, sys, os, json, warnings
    warnings.filterwarnings("ignore")
    resource.setrlimit(resource.RLIMIT_AS, (__MEM_BYTES__, __MEM_BYTES__))
    resource.setrlimit(resource.RLIMIT_CPU, (__CPU_SECONDS__, __CPU_SECONDS__))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (512 * 1024 * 1024, 512 * 1024 * 1024))
    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.path.insert(0, os.getcwd())
""")

SESSIONS: dict[str, Path] = {}


def _session_dir(session: str | None) -> Path:
    if session and session in SESSIONS:
        return SESSIONS[session]
    sid = session or uuid.uuid4().hex[:10]
    d = settings.data_dir / "notebooks" / sid
    d.mkdir(parents=True, exist_ok=True)
    SESSIONS[sid] = d
    return d


def run_python(code: str, session: str | None = None, timeout: int | None = None,
               project_id: str | None = None) -> dict:
    if not settings.allow_code_exec:
        raise PermissionError("Code execution is disabled on this BioIDE instance (BIOIDE_ALLOW_CODE_EXEC=0).")
    sid = session or uuid.uuid4().hex[:10]
    d = _session_dir(sid)
    timeout = timeout or settings.exec_timeout_s
    mem = settings.exec_mem_mb * 1024 * 1024
    pre = PREAMBLE.replace("__MEM_BYTES__", str(mem)).replace("__CPU_SECONDS__", str(timeout))
    # State carries between cells through a file in the session directory.
    script = (pre
              + "\n_bioide_state = {}\n"
              + f"_p = os.path.join({str(d)!r}, '_state.json')\n"
              + "if os.path.exists(_p):\n"
              + "    _bioide_state = json.load(open(_p))\n"
              + "globals().update({k: v for k, v in _bioide_state.items() if not k.startswith('_')})\n"
              + "\n# ---- user cell ----\n" + code + "\n# ---- end cell ----\n"
              + textwrap.dedent("""
                  _keep = {}
                  for _k, _v in list(globals().items()):
                      if _k.startswith('_') or _k in {'resource','sys','os','json','warnings'}:
                          continue
                      if isinstance(_v, (int, float, str, bool, list, dict, type(None))):
                          try:
                              json.dumps(_v); _keep[_k] = _v
                          except Exception:
                              pass
                  json.dump(_keep, open(_p, 'w'))
                  """))
    with tempfile.NamedTemporaryFile("w", suffix=".py", dir=d, delete=False) as fh:
        fh.write(script)
        path = fh.name
    rid = store.start_run("code_execution", "python", sys.version.split()[0],
                          {"session": sid, "timeout_s": timeout, "mem_mb": settings.exec_mem_mb,
                           "code_lines": code.count("\n") + 1}, project_id=project_id)
    t0 = time.time()
    before = {p.name for p in d.iterdir()}
    try:
        p = subprocess.run([sys.executable, "-I", path], capture_output=True, text=True, cwd=d, timeout=timeout,
                           env={**os.environ, "PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg", "OMP_NUM_THREADS": "2"})
        status = "succeeded" if p.returncode == 0 else "failed"
        out = {"status": status, "returncode": p.returncode,
               "stdout": p.stdout[-60000:], "stderr": p.stderr[-20000:],
               "truncated": len(p.stdout) > 60000}
    except subprocess.TimeoutExpired:
        status = "timeout"
        out = {"status": status, "returncode": None, "stdout": "", "stderr":
               f"Execution exceeded {timeout}s and was terminated. "
               "Raise BIOIDE_EXEC_TIMEOUT, or move long jobs to a workflow engine.", "truncated": False}
    finally:
        Path(path).unlink(missing_ok=True)
    new_files = sorted(p_.name for p_ in d.iterdir() if p_.name not in before and not p_.name.startswith("_"))
    store.finish_run(rid, status, {"returncode": out.get("returncode"), "new_files": new_files},
                     None if status == "succeeded" else (out.get("stderr") or "")[:2000])
    return {**out, "session": sid, "duration_s": round(time.time() - t0, 3), "run_id": rid,
            "working_dir": str(d), "new_files": new_files,
            "limits": {"timeout_s": timeout, "memory_mb": settings.exec_mem_mb, "max_file_mb": 512},
            "isolation": "Separate process with address-space, CPU, process-count and file-size limits. "
                         "This is resource isolation, not a security boundary: the code runs as the backend user. "
                         "Do not expose this endpoint on a shared host without container isolation."}


def list_session_files(session: str) -> list[dict]:
    d = _session_dir(session)
    return [{"name": p.name, "size_bytes": p.stat().st_size, "modified": p.stat().st_mtime}
            for p in sorted(d.iterdir()) if p.is_file() and not p.name.startswith("_")]


def read_session_file(session: str, name: str, max_bytes: int = 2_000_000) -> dict:
    d = _session_dir(session)
    safe = Path(name).name
    p = (d / safe).resolve()
    if not str(p).startswith(str(d.resolve())) or not p.is_file():
        raise FileNotFoundError(f"No such file in this session: {safe}")
    data = p.read_bytes()[:max_bytes]
    try:
        return {"name": safe, "text": data.decode(), "size_bytes": p.stat().st_size, "binary": False}
    except UnicodeDecodeError:
        import base64
        return {"name": safe, "base64": base64.b64encode(data).decode(), "size_bytes": p.stat().st_size, "binary": True}
