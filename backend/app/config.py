"""Runtime configuration. Everything is read from environment variables so the
LLM provider, storage location and execution permissions stay configurable."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _flag(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("BIOIDE_DATA_DIR", Path.home() / ".bioide")))

    # LLM provider: "anthropic" | "openai" (any OpenAI-compatible endpoint, incl. local Ollama/vLLM) | "none"
    llm_provider: str = field(default_factory=lambda: os.getenv("BIOIDE_LLM_PROVIDER", "").lower())
    llm_model: str = field(default_factory=lambda: os.getenv("BIOIDE_LLM_MODEL", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("BIOIDE_LLM_BASE_URL", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # Literature APIs ask for a contact email in polite-pool requests (optional).
    contact_email: str = field(default_factory=lambda: os.getenv("BIOIDE_CONTACT_EMAIL", ""))
    ncbi_api_key: str = field(default_factory=lambda: os.getenv("NCBI_API_KEY", ""))

    # Execution permissions. Both still require per-run approval from the UI.
    allow_code_exec: bool = field(default_factory=lambda: _flag("BIOIDE_ALLOW_CODE_EXEC", True))
    allow_local_install: bool = field(default_factory=lambda: _flag("BIOIDE_ALLOW_LOCAL_INSTALL", False))
    exec_timeout_s: int = field(default_factory=lambda: int(os.getenv("BIOIDE_EXEC_TIMEOUT", "120")))
    exec_mem_mb: int = field(default_factory=lambda: int(os.getenv("BIOIDE_EXEC_MEM_MB", "2048")))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("BIOIDE_MAX_UPLOAD_MB", "50")))

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "projects").mkdir(exist_ok=True)
        if not self.llm_provider:
            if self.anthropic_api_key:
                self.llm_provider = "anthropic"
            elif self.openai_api_key or self.llm_base_url:
                self.llm_provider = "openai"
            else:
                self.llm_provider = "none"
        if not self.llm_model:
            self.llm_model = {"anthropic": "claude-sonnet-4-5", "openai": "gpt-4o-mini"}.get(self.llm_provider, "")

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider in {"anthropic", "openai"}

    def public(self) -> dict:
        return {
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_enabled": self.llm_enabled,
            "allow_code_exec": self.allow_code_exec,
            "allow_local_install": self.allow_local_install,
            "exec_timeout_s": self.exec_timeout_s,
            "max_upload_mb": self.max_upload_mb,
            "data_dir": str(self.data_dir),
        }


settings = Settings()
APP_DIR = Path(__file__).parent
SAMPLES_DIR = APP_DIR / "data" / "samples"
