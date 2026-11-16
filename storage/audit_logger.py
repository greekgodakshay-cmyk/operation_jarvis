"""
Structured Audit Logger and Execution Tracing Engine.
Provides immutable JSONL execution traces with secret redaction and rolling hash verification.
"""
import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from config.settings import settings
from security.secret_redactor import redact_structure

class AuditLogger:
    def __init__(self, audit_path: Optional[Path] = None, traces_dir: Optional[Path] = None):
        self.audit_path = audit_path or settings.audit_log_path
        self.traces_dir = traces_dir or settings.traces_dir
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_hash = self._recover_last_hash()

    def _recover_last_hash(self) -> str:
        """Recovers the latest rolling hash from disk to maintain chain continuity across restarts."""
        if not self.audit_path.exists():
            return "GENESIS_HASH_JARVIS_INIT"
        try:
            with open(self.audit_path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
                if lines:
                    last_entry = json.loads(lines[-1])
                    return last_entry.get("hash", "GENESIS_HASH_JARVIS_INIT")
        except Exception:
            pass
        return "GENESIS_HASH_JARVIS_INIT"

    def verify_chain(self, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Cryptographically validates the SHA-256 hash chain in an audit log file.
        Detects tampering, missing records, reordering, and corrupted hashes.
        """
        target = file_path or self.audit_path
        if not target.exists():
            return {"ok": True, "total_entries": 0, "message": "Log file does not exist yet."}

        with open(target, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        if not lines:
            return {"ok": True, "total_entries": 0, "message": "Empty log file."}

        expected_prev = "GENESIS_HASH_JARVIS_INIT"
        for idx, line in enumerate(lines):
            try:
                entry = json.loads(line)
            except Exception as e:
                return {
                    "ok": False,
                    "broken_index": idx,
                    "error": f"JSON parse error on entry {idx}: {e}"
                }

            claimed_hash = entry.get("hash")
            prev_hash = entry.get("prev_hash")

            # Check chain continuity
            if prev_hash != expected_prev:
                return {
                    "ok": False,
                    "broken_index": idx,
                    "error": f"Chain link broken at entry {idx}: claimed prev_hash '{prev_hash}' != expected '{expected_prev}'"
                }

            # Recompute hash over unhashed fields
            entry_copy = {
                "timestamp": entry.get("timestamp"),
                "task_id": entry.get("task_id"),
                "event_type": entry.get("event_type"),
                "prev_hash": prev_hash,
                "details": entry.get("details", {})
            }
            computed_hash = hashlib.sha256(json.dumps(entry_copy, sort_keys=True).encode("utf-8")).hexdigest()

            if computed_hash != claimed_hash:
                return {
                    "ok": False,
                    "broken_index": idx,
                    "error": f"Hash mismatch at entry {idx}: computed '{computed_hash}' != claimed '{claimed_hash}' (tampering detected)"
                }

            expected_prev = claimed_hash

        return {
            "ok": True,
            "total_entries": len(lines),
            "last_hash": expected_prev,
            "message": f"Successfully verified {len(lines)} audit entries. Integrity 100% valid."
        }

    def log_event(self, task_id: str, event_type: str, details: Dict[str, Any]) -> str:
        """
        Appends an event to both the global audit trail and the task trace file.
        Returns the event entry hash.
        """
        now = datetime.now().isoformat()
        clean_details = redact_structure(details)

        with self._lock:
            # Build entry
            entry = {
                "timestamp": now,
                "task_id": task_id,
                "event_type": event_type,
                "prev_hash": self._last_hash,
                "details": clean_details
            }
            entry_str = json.dumps(entry, sort_keys=True)
            current_hash = hashlib.sha256(entry_str.encode("utf-8")).hexdigest()
            entry["hash"] = current_hash
            self._last_hash = current_hash

            serialized = json.dumps(entry) + "\n"

            # Global audit log
            with open(self.audit_path, "a", encoding="utf-8") as f:
                f.write(serialized)

            # Per-task trace file
            task_trace_file = self.traces_dir / f"{task_id}.jsonl"
            with open(task_trace_file, "a", encoding="utf-8") as f:
                f.write(serialized)

            return current_hash

    def get_task_trace(self, task_id: str) -> list:
        task_trace_file = self.traces_dir / f"{task_id}.jsonl"
        if not task_trace_file.exists():
            return []
        events = []
        with open(task_trace_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events

audit_logger = AuditLogger()
