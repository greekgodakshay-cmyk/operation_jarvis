"""
Strongly-typed Configuration and Runtime Settings for Operation Jarvis.
"""
import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class JarvisSettings(BaseModel):
    # LLM & Ollama Configuration
    ollama_api_url: str = Field(default="http://127.0.0.1:11434")
    primary_model: str = Field(default="qwen3.5:9b")
    fallback_model: str = Field(default="qwen-batman:latest")
    temperature: float = Field(default=0.2)
    max_tokens: int = Field(default=4096)
    llm_request_timeout: float = Field(default=120.0)

    # Memory Ecosystem Configuration
    memory_root: Path = Field(default=Path(r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY"))
    memory_db_path: Path = Field(default=Path(r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\07_MEMORY_INDEX\memory.db"))
    memory_config_path: Path = Field(default=Path(r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\STORAGE_CONFIG.json"))
    
    # Task & Execution State
    task_db_path: Path = Field(default=PROJECT_ROOT / "data" / "jarvis_tasks.db")
    audit_log_path: Path = Field(default=PROJECT_ROOT / "logs" / "audit_trail.jsonl")
    traces_dir: Path = Field(default=PROJECT_ROOT / "logs" / "traces")
    
    # Execution Limits & Guardrails
    max_steps_per_task: int = Field(default=15)
    max_retries_per_step: int = Field(default=3)
    step_timeout_seconds: float = Field(default=60.0)
    task_timeout_seconds: float = Field(default=600.0)

    # Security & Path Jailing
    allowed_workspace_roots: List[Path] = Field(default_factory=lambda: [
        Path(r"C:\Users\Akshay aravind .rv\operation_jarvis"),
        Path(r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY"),
        Path(r"C:\Users\Akshay aravind .rv")
    ])
    forbidden_directories: List[str] = Field(default_factory=lambda: [
        r"C:\Windows",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\System Volume Information",
        r"C:\$Recycle.Bin"
    ])
    
    # API & Networking
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000)

    # Dedicated Persistent Chrome Browser Configuration
    chrome_executable: Path = Field(default=Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"))
    jarvis_chrome_profile: Path = Field(default=Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Akshay aravind .rv\AppData\Local")) / "OperationJARVIS" / "ChromeProfile")
    chrome_debugging_port: int = Field(default=9222)

    # Ecosystem discovery paths
    mcp_config_path: Path = Field(default=Path(r"C:\Users\Akshay aravind .rv\.gemini\config\mcp_config.json"))
    plugins_dir: Path = Field(default=Path(r"C:\Users\Akshay aravind .rv\.gemini\config\plugins"))
    builtin_skills_dir: Path = Field(default=Path(r"C:\Users\Akshay aravind .rv\.gemini\antigravity-cli\builtin\skills"))
    agent_skills_dir: Path = Field(default=Path(r"C:\Users\Akshay aravind .rv\.gemini\config\plugins\agent-skills\skills"))
    ponytail_skills_dir: Path = Field(default=Path(r"C:\Users\Akshay aravind .rv\.gemini\config\plugins\ponytail\skills"))
    voice_engine_dir: Path = Field(default=Path(r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\engine\voice"))

# Global default instance
settings = JarvisSettings()

# Ensure directories exist
settings.task_db_path.parent.mkdir(parents=True, exist_ok=True)
settings.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
settings.traces_dir.mkdir(parents=True, exist_ok=True)
