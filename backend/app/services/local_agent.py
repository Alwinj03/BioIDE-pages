"""Local environment inspection and approved command execution.

Design rules, enforced here rather than left to the UI:
  * Nothing runs without an explicit approval token for that exact command string.
  * Installation commands are generated, never auto-run.
  * Every attempt is written to the command log, approved or not.
  * No shell interpolation: commands are tokenised and run without a shell.

This module runs where the backend runs. When the backend is on the user's own
machine (the normal deployment for BioIDE) that is the user's environment. When
the backend is remote, this inspects the server, which the API response states.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import time
from typing import Any

import psutil

from ..config import settings
from ..store import store

_SECRET = secrets.token_bytes(32)  # per-process: approvals do not survive a restart

TOOL_PROBES = {
    "python": ["python3", "--version"], "conda": ["conda", "--version"], "mamba": ["mamba", "--version"],
    "pixi": ["pixi", "--version"], "docker": ["docker", "--version"], "apptainer": ["apptainer", "--version"],
    "singularity": ["singularity", "--version"], "nextflow": ["nextflow", "-version"],
    "snakemake": ["snakemake", "--version"], "R": ["R", "--version"], "java": ["java", "-version"],
    "blastp": ["blastp", "-version"], "diamond": ["diamond", "--version"], "hmmsearch": ["hmmsearch", "-h"],
    "mafft": ["mafft", "--version"], "muscle": ["muscle", "-version"],
    "fastp": ["fastp", "--version"], "multiqc": ["multiqc", "--version"],
    "bwa-mem2": ["bwa-mem2", "version"], "bowtie2": ["bowtie2", "--version"], "minimap2": ["minimap2", "--version"],
    "samtools": ["samtools", "--version"], "bcftools": ["bcftools", "--version"],
    "STAR": ["STAR", "--version"], "hisat2": ["hisat2", "--version"], "salmon": ["salmon", "--version"],
    "kallisto": ["kallisto", "version"], "featureCounts": ["featureCounts", "-v"],
    "kraken2": ["kraken2", "--version"], "bracken": ["bracken", "-v"], "metaphlan": ["metaphlan", "--version"],
    "humann": ["humann", "--version"], "qiime": ["qiime", "--version"],
    "prokka": ["prokka", "--version"], "bakta": ["bakta", "--version"], "pyrodigal": ["pyrodigal", "--version"],
    "run_dbcan": ["run_dbcan", "--version"], "emapper.py": ["emapper.py", "--version"],
    "foldseek": ["foldseek", "version"], "pymol": ["pymol", "-cq", "-d", "print(cmd.get_version()[0])"],
    "gmx": ["gmx", "--version"], "vina": ["vina", "--version"],
}

PY_LIBS = ["cobra", "Bio", "pydeseq2", "pandas", "numpy", "scipy", "sklearn", "anndata", "scanpy",
           "pyopenms", "micom", "memote", "cameo", "tellurium", "basico", "openmm", "pyrodigal", "escher"]

DANGEROUS = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rf]", re.I), "recursive or forced deletion"),
    (re.compile(r"\b(mkfs|fdisk|dd)\b", re.I), "disk or filesystem operation"),
    (re.compile(r"\b(shutdown|reboot|halt|poweroff)\b", re.I), "machine power state change"),
    (re.compile(r"\bchmod\s+(-R\s+)?[0-7]*777\b"), "world-writable permissions"),
    (re.compile(r"\b(curl|wget)\b[^|;]*\|\s*(ba)?sh", re.I), "piping a download straight into a shell"),
    (re.compile(r">\s*/dev/(sd|nvme|disk)", re.I), "writing to a raw device"),
    (re.compile(r"\b(sudo|doas|su)\b"), "privilege escalation"),
    (re.compile(r":\(\)\s*\{.*\};\s*:"), "fork bomb"),
    (re.compile(r"\b(nc|ncat|netcat)\b.*-e", re.I), "reverse shell"),
    (re.compile(r"/etc/(passwd|shadow|sudoers)"), "access to system credential files"),
    (re.compile(r"~/\.(ssh|aws|gnupg)|\.ssh/id_"), "access to private keys or cloud credentials"),
    (re.compile(r"\bgit\s+push\b", re.I), "pushing to a remote repository"),
]
SHELL_META = re.compile(r"[;&|><`$\n]|\$\(|\&\&|\|\|")


def _probe(cmd: list[str], timeout: int = 8) -> tuple[bool, str]:
    exe = shutil.which(cmd[0])
    if not exe:
        return False, ""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        m = re.search(r"\d+\.\d+(\.\d+)?", out)
        return True, (m.group(0) if m else out.splitlines()[0][:80] if out else "present")
    except Exception as exc:
        return True, f"present (version probe failed: {type(exc).__name__})"


def inspect_environment(deep: bool = False) -> dict:
    vm = psutil.virtual_memory()
    du = shutil.disk_usage(str(settings.data_dir))
    tools, missing = {}, []
    probes = TOOL_PROBES if deep else {k: v for k, v in TOOL_PROBES.items()
                                       if k in {"python", "conda", "mamba", "docker", "nextflow", "snakemake", "R", "java",
                                                "samtools", "blastp", "fastp", "salmon", "kraken2", "metaphlan"}}
    for name, cmd in probes.items():
        found, ver = _probe(cmd)
        if found:
            tools[name] = {"found": True, "version": ver, "path": shutil.which(cmd[0])}
        else:
            missing.append(name)
    libs = {}
    for lib in PY_LIBS:
        try:
            mod = __import__(lib)
            libs[lib] = getattr(mod, "__version__", "unknown")
        except Exception:
            libs[lib] = None
    envs: list[str] = []
    if shutil.which("conda"):
        try:
            p = subprocess.run(["conda", "env", "list", "--json"], capture_output=True, text=True, timeout=25)
            import json as _json
            envs = _json.loads(p.stdout).get("envs", [])
        except Exception:
            envs = []
    return {
        "backend_host": {
            "hostname": platform.node(), "platform": platform.platform(), "machine": platform.machine(),
            "python": sys.version.split()[0], "cwd": os.getcwd(),
        },
        "where_this_runs": "This describes the machine the BioIDE backend process is on. "
                           "If you are using a hosted BioIDE instance, it is not your laptop.",
        "resources": {
            "cpu_logical": psutil.cpu_count(), "cpu_physical": psutil.cpu_count(logical=False),
            "ram_total_gb": round(vm.total / 1e9, 2), "ram_available_gb": round(vm.available / 1e9, 2),
            "disk_total_gb": round(du.total / 1e9, 1), "disk_free_gb": round(du.free / 1e9, 1),
            "load_avg": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        },
        "tools_found": tools, "tools_missing": sorted(missing),
        "python_libraries": libs,
        "conda_environments": envs,
        "containers": {"docker": shutil.which("docker") is not None,
                       "apptainer": shutil.which("apptainer") is not None or shutil.which("singularity") is not None},
        "permissions": {"code_execution_enabled": settings.allow_code_exec,
                        "install_execution_enabled": settings.allow_local_install,
                        "note": "Even when enabled, each command needs an explicit approval token."},
        "deep_probe": deep,
    }


def feasibility(tool_id: str) -> dict:
    """Can this catalogue tool actually run here, and if not, what is missing?"""
    from . import catalogue
    t = catalogue.TOOLS.get(tool_id)
    if not t:
        raise KeyError(f"Unknown tool '{tool_id}'")
    env = inspect_environment(deep=True)
    binaries = {"blast": "blastp", "bakta": "bakta", "prokka": "prokka", "kraken2": "kraken2",
                "metaphlan": "metaphlan", "humann": "humann", "salmon": "salmon", "star": "STAR",
                "hisat2": "hisat2", "samtools": "samtools", "bcftools": "bcftools", "fastp": "fastp",
                "mafft": "mafft", "muscle": "muscle", "diamond": "diamond", "hmmer": "hmmsearch",
                "bwa-mem2": "bwa-mem2", "bowtie2": "bowtie2", "minimap2": "minimap2",
                "featurecounts": "featureCounts", "kallisto": "kallisto", "qiime2": "qiime",
                "dbcan": "run_dbcan", "eggnog-mapper": "emapper.py", "foldseek": "foldseek",
                "nextflow": "nextflow", "snakemake": "snakemake", "multiqc": "multiqc",
                "pymol": "pymol", "gromacs": "gmx", "vina": "vina", "bracken": "bracken"}
    libs = {"cobrapy": "cobra", "biopython": "Bio", "pydeseq2": "pydeseq2", "pyrodigal": "pyrodigal",
            "openms": "pyopenms", "micom": "micom", "memote": "memote", "cameo": "cameo",
            "tellurium": "tellurium", "copasi": "basico", "openmm": "openmm", "escher": "escher"}
    installed, detail = False, ""
    if tool_id in libs:
        v = env["python_libraries"].get(libs[tool_id])
        installed, detail = v is not None, f"python package '{libs[tool_id]}' version {v}" if v else f"python package '{libs[tool_id]}' not importable"
    elif tool_id in binaries:
        info = env["tools_found"].get(binaries[tool_id])
        installed = info is not None
        detail = f"{binaries[tool_id]} {info['version']} at {info['path']}" if info else f"binary '{binaries[tool_id]}' not on PATH"
    else:
        detail = "No local-detection rule for this tool; it is a hosted or GUI application."

    blockers = []
    if t.execution == "external":
        blockers.append("This tool is not something BioIDE runs for you; use the hosted service or desktop application.")
    if t.execution == "local_db" and installed:
        blockers.append(f"Installed, but it needs a reference database: {t.resources}")
    ram = env["resources"]["ram_total_gb"]
    if tool_id in {"star", "kraken2"} and ram < 16:
        blockers.append(f"This machine has {ram} GB RAM; standard references for {t.name} need more. "
                        + ("Use HISAT2 or Salmon." if tool_id == "star" else "Use a capped database, or MetaPhlAn."))
    return {
        "tool": tool_id, "name": t.name, "execution_class": t.execution,
        "execution_meaning": catalogue.EXECUTION_MEANING[t.execution],
        "installed": installed, "detection": detail,
        "install_options": t.install, "docs": t.docs,
        "install_commands": [{"manager": k, "command": v} for k, v in t.install.items()],
        "alternatives": t.alternatives, "resources": t.resources,
        "blockers": blockers,
        "can_run_now": bool(installed and not blockers and t.execution in {"native", "local"}),
        "machine": {"ram_total_gb": ram, "cpu_logical": env["resources"]["cpu_logical"],
                    "disk_free_gb": env["resources"]["disk_free_gb"]},
    }


# ------------------------------------------------------------------ approvals

def _is_install(cmd: str) -> bool:
    return bool(re.search(r"\b(pip|pip3|conda|mamba|micromamba|pixi|apt|apt-get|brew|npm|docker\s+pull)\b", cmd))


def review(command: str, project_id: str | None = None) -> dict:
    """Static review of a command, returning an approval token if it may be run.
    The token is bound to the exact command string."""
    cmd = command.strip()
    risks = [why for rx, why in DANGEROUS if rx.search(cmd)]
    meta = bool(SHELL_META.search(cmd))
    install = _is_install(cmd)
    allowed = settings.allow_code_exec and not risks and not meta
    if install and not settings.allow_local_install:
        allowed = False
    reasons = []
    if risks:
        reasons += [f"refused: {r}" for r in risks]
    if meta:
        reasons.append("refused: shell metacharacters (;, |, &, >, <, backtick, $()) are not executed. "
                       "Run one command per call, or write a script file and run that explicitly.")
    if install and not settings.allow_local_install:
        reasons.append("install commands are disabled (set BIOIDE_ALLOW_LOCAL_INSTALL=1 to allow them). "
                       "Run the command yourself in a terminal instead.")
    if not settings.allow_code_exec:
        reasons.append("command execution is disabled for this BioIDE instance (BIOIDE_ALLOW_CODE_EXEC=0).")
    exe = cmd.split()[0] if cmd else ""
    resolved = shutil.which(exe) if exe else None
    if allowed and not resolved:
        allowed = False
        reasons.append(f"'{exe}' was not found on PATH. Install it first; BioIDE will not install it for you.")
    token = None
    if allowed:
        expiry = int(time.time()) + 600
        sig = hmac.new(_SECRET, f"{cmd}|{expiry}".encode(), hashlib.sha256).hexdigest()[:32]
        token = f"{expiry}.{sig}"
    store.log_command(cmd, approved=False, status="reviewed" if allowed else "refused", project_id=project_id)
    return {"command": cmd, "is_install": install, "resolved_binary": resolved,
            "approval_required": True, "may_execute": allowed, "reasons": reasons,
            "approval_token": token, "token_expires_in_s": 600 if token else None,
            "note": "Nothing has run. Submit this token with the identical command to execute it."}


def execute(command: str, approval_token: str, cwd: str | None = None, timeout: int | None = None,
            project_id: str | None = None) -> dict:
    cmd = command.strip()
    try:
        expiry_s, sig = approval_token.split(".", 1)
        expiry = int(expiry_s)
    except Exception:
        raise PermissionError("Malformed approval token.")
    expected = hmac.new(_SECRET, f"{cmd}|{expiry}".encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expected):
        store.log_command(cmd, approved=False, status="rejected_bad_token", project_id=project_id)
        raise PermissionError("The approval token does not match this command. Re-review the command you intend to run.")
    if time.time() > expiry:
        store.log_command(cmd, approved=False, status="rejected_expired", project_id=project_id)
        raise PermissionError("The approval token has expired. Review the command again.")
    rv = review(cmd, project_id)
    if not rv["may_execute"]:
        store.log_command(cmd, approved=False, status="rejected_on_recheck", project_id=project_id)
        raise PermissionError("Refused on re-check: " + "; ".join(rv["reasons"]))

    import shlex
    argv = shlex.split(cmd)
    work = cwd or str(settings.data_dir / "work")
    os.makedirs(work, exist_ok=True)
    t0 = time.time()
    cid = store.log_command(cmd, approved=True, status="running", project_id=project_id)
    try:
        p = subprocess.run(argv, capture_output=True, text=True, cwd=work,
                           timeout=timeout or settings.exec_timeout_s,
                           env={**os.environ, "PYTHONUNBUFFERED": "1"})
        out = {"command": cmd, "argv": argv, "cwd": work, "returncode": p.returncode,
               "stdout": p.stdout[-40000:], "stderr": p.stderr[-40000:],
               "stdout_truncated": len(p.stdout) > 40000, "duration_s": round(time.time() - t0, 3),
               "status": "succeeded" if p.returncode == 0 else "failed", "command_log_id": cid}
    except subprocess.TimeoutExpired as exc:
        out = {"command": cmd, "argv": argv, "cwd": work, "returncode": None,
               "stdout": (exc.stdout or b"").decode(errors="replace")[-20000:] if isinstance(exc.stdout, bytes) else (exc.stdout or "")[-20000:],
               "stderr": f"Timed out after {timeout or settings.exec_timeout_s}s and was killed.",
               "duration_s": round(time.time() - t0, 3), "status": "timeout", "command_log_id": cid}
    store.log_command(cmd, approved=True, status=out["status"], returncode=out.get("returncode"), project_id=project_id)
    return out


def install_plan(tool_id: str) -> dict:
    """Produce installation commands without running anything."""
    f = feasibility(tool_id)
    if f["installed"]:
        return {**f, "plan": [], "message": f"{f['name']} is already available: {f['detection']}"}
    plan = []
    for manager, command in f["install_options"].items():
        plan.append({"manager": manager, "command": command,
                     "available_here": shutil.which(command.split()[0]) is not None if command and not command.startswith(("see ", "Download", "Windows", "git ")) else None,
                     "run_it_yourself": not settings.allow_local_install})
    return {**f, "plan": plan,
            "message": f"{f['name']} is not installed. "
                       + ("Copy a command below into your own terminal; BioIDE will not install software for you."
                          if not settings.allow_local_install
                          else "Submit a command for review, then execute it with the returned approval token."),
            "database_requirement": f["resources"] or None}
