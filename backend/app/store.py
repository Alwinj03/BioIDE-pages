"""SQLite-backed project store with run provenance and version history.

Every computational result BioIDE shows is written here as a *run* with the
tool, tool version, parameters, input fingerprint, status and timing, so
results are always traceable to an actual execution."""
from __future__ import annotations

import hashlib
import json
import platform
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, objective TEXT,
  sample_id TEXT, created REAL, updated REAL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, project_id TEXT, kind TEXT, tool TEXT, tool_version TEXT,
  params TEXT, input_hash TEXT, status TEXT, error TEXT, summary TEXT,
  started REAL, finished REAL, host TEXT
);
CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY, project_id TEXT, kind TEXT, name TEXT, version INTEGER,
  content TEXT, created REAL
);
CREATE TABLE IF NOT EXISTS commands (
  id TEXT PRIMARY KEY, project_id TEXT, command TEXT, approved INTEGER,
  status TEXT, returncode INTEGER, created REAL
);
CREATE TABLE IF NOT EXISTS literature (
  project_id TEXT, key TEXT, record TEXT, created REAL, PRIMARY KEY (project_id, key)
);
"""

_lock = threading.Lock()


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or settings.data_dir / "bioide.sqlite3")
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with _lock:
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    # ---------- projects ----------
    def create_project(self, name: str, description: str = "", objective: str = "", sample_id: str | None = None) -> dict:
        pid = uuid.uuid4().hex[:12]
        now = time.time()
        with self._conn() as c:
            c.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?)", (pid, name, description, objective, sample_id, now, now))
        self.project_dir(pid).mkdir(parents=True, exist_ok=True)
        return self.get_project(pid)

    def project_dir(self, pid: str) -> Path:
        safe = "".join(ch for ch in pid if ch.isalnum())
        return settings.data_dir / "projects" / safe

    def get_project(self, pid: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        return dict(row) if row else None

    def list_projects(self) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM projects ORDER BY updated DESC")]

    def find_sample_project(self, sample_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM projects WHERE sample_id=? ORDER BY created LIMIT 1", (sample_id,)).fetchone()
        return dict(row) if row else None

    def delete_project(self, pid: str) -> None:
        with self._conn() as c:
            for t in ("projects",):
                c.execute(f"DELETE FROM {t} WHERE id=?", (pid,))
            for t in ("runs", "artifacts", "commands", "literature"):
                c.execute(f"DELETE FROM {t} WHERE project_id=?", (pid,))
        d = self.project_dir(pid)
        if d.exists():
            import shutil
            shutil.rmtree(d)

    def touch(self, pid: str | None) -> None:
        if pid:
            with self._conn() as c:
                c.execute("UPDATE projects SET updated=? WHERE id=?", (time.time(), pid))

    # ---------- runs / provenance ----------
    def start_run(self, kind: str, tool: str, tool_version: str, params: dict, input_hash: str = "", project_id: str | None = None) -> str:
        rid = uuid.uuid4().hex[:16]
        with self._conn() as c:
            c.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rid, project_id, kind, tool, tool_version, json.dumps(params, default=str), input_hash,
                 "running", None, None, time.time(), None, f"{platform.node()} / {platform.platform()}"),
            )
        self.touch(project_id)
        return rid

    def finish_run(self, rid: str, status: str, summary: Any = None, error: str | None = None) -> None:
        with self._conn() as c:
            c.execute("UPDATE runs SET status=?, summary=?, error=?, finished=? WHERE id=?",
                      (status, json.dumps(summary, default=str)[:20000] if summary is not None else None, error, time.time(), rid))

    def get_run(self, rid: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
        return _run(row) if row else None

    def list_runs(self, project_id: str | None = None, limit: int = 200) -> list[dict]:
        with self._conn() as c:
            if project_id:
                rows = c.execute("SELECT * FROM runs WHERE project_id=? ORDER BY started DESC LIMIT ?", (project_id, limit))
            else:
                rows = c.execute("SELECT * FROM runs ORDER BY started DESC LIMIT ?", (limit,))
            return [_run(r) for r in rows]

    # ---------- versioned artifacts (workflows, scripts, reports) ----------
    def save_artifact(self, project_id: str, kind: str, name: str, content: Any) -> dict:
        with self._conn() as c:
            row = c.execute("SELECT MAX(version) v FROM artifacts WHERE project_id=? AND kind=? AND name=?", (project_id, kind, name)).fetchone()
            version = (row["v"] or 0) + 1
            aid = uuid.uuid4().hex[:12]
            c.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?,?)",
                      (aid, project_id, kind, name, version, json.dumps(content, default=str), time.time()))
        self.touch(project_id)
        return {"id": aid, "kind": kind, "name": name, "version": version}

    def list_artifacts(self, project_id: str, kind: str | None = None, latest_only: bool = True) -> list[dict]:
        q = "SELECT * FROM artifacts WHERE project_id=?" + (" AND kind=?" if kind else "") + " ORDER BY name, version"
        args = (project_id, kind) if kind else (project_id,)
        with self._conn() as c:
            rows = [dict(r) for r in c.execute(q, args)]
        for r in rows:
            r["content"] = json.loads(r["content"])
        if latest_only:
            latest: dict[tuple, dict] = {}
            for r in rows:
                latest[(r["kind"], r["name"])] = r
            rows = list(latest.values())
        return rows

    def artifact_history(self, project_id: str, kind: str, name: str) -> list[dict]:
        with self._conn() as c:
            rows = [dict(r) for r in c.execute(
                "SELECT id, version, created FROM artifacts WHERE project_id=? AND kind=? AND name=? ORDER BY version DESC",
                (project_id, kind, name))]
        return rows

    # ---------- local command log ----------
    def log_command(self, command: str, approved: bool, status: str, returncode: int | None = None, project_id: str | None = None) -> str:
        cid = uuid.uuid4().hex[:12]
        with self._conn() as c:
            c.execute("INSERT INTO commands VALUES (?,?,?,?,?,?,?)", (cid, project_id, command, int(approved), status, returncode, time.time()))
        return cid

    def list_commands(self, limit: int = 200) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM commands ORDER BY created DESC LIMIT ?", (limit,))]

    # ---------- literature collection ----------
    def save_paper(self, project_id: str, record: dict) -> None:
        key = record.get("doi") or record.get("pmid") or record.get("id") or record.get("title", "")[:80]
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO literature VALUES (?,?,?,?)", (project_id, key, json.dumps(record), time.time()))

    def list_papers(self, project_id: str) -> list[dict]:
        with self._conn() as c:
            return [json.loads(r["record"]) for r in c.execute("SELECT record FROM literature WHERE project_id=? ORDER BY created", (project_id,))]

    def remove_paper(self, project_id: str, key: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM literature WHERE project_id=? AND key=?", (project_id, key))


def _run(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["params"] = json.loads(d["params"]) if d.get("params") else {}
    d["summary"] = json.loads(d["summary"]) if d.get("summary") else None
    if d.get("finished") and d.get("started"):
        d["duration_s"] = round(d["finished"] - d["started"], 3)
    return d


def fingerprint(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()[:16]


store = Store()


class tracked_run:
    """Context manager that records a computation as a provenance run.

    with tracked_run("fba", "cobrapy", cobra.__version__, params, project_id=pid) as run:
        ... compute ...
        run.summary = {...}
    """

    def __init__(self, kind: str, tool: str, tool_version: str, params: dict, input_hash: str = "", project_id: str | None = None):
        self.args = (kind, tool, tool_version, params, input_hash, project_id)
        self.summary: Any = None
        self.id = ""

    def __enter__(self) -> "tracked_run":
        kind, tool, ver, params, ih, pid = self.args
        self.id = store.start_run(kind, tool, ver, params, ih, pid)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is None:
            store.finish_run(self.id, "succeeded", self.summary)
        else:
            store.finish_run(self.id, "failed", self.summary, f"{exc_type.__name__}: {exc}")
        return False

    def provenance(self) -> dict:
        kind, tool, ver, params, ih, pid = self.args
        return {"run_id": self.id, "tool": tool, "tool_version": ver, "kind": kind, "input_hash": ih,
                "executed": True, "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
