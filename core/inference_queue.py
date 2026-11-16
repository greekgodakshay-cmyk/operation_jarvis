"""
Centralized GPU Inference Queue & Concurrency Controller for Operation JARVIS.
Optimized for HP Victus (NVIDIA RTX 4050 Laptop GPU, 6 GB VRAM).
Serializes model calls by priority to prevent concurrent GPU VRAM thrashing and CUDA OOM.
"""
import heapq
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("jarvis.inference_queue")

class InferencePriority(IntEnum):
    VOICE_INTERACTIVE = 0   # Real-time voice / urgent interactive queries
    ORCHESTRATION = 1       # Master planning and subagent coordination
    TOOL_EXECUTION = 2      # Function calling and self-correction
    BACKGROUND_INDEXING = 3 # Memory indexing, document ingest, background tasks

@dataclass(order=True)
class QueuedInferenceRequest:
    priority: int
    timestamp: float
    request_id: str = field(compare=False)
    func: Callable[..., Any] = field(compare=False)
    args: Tuple = field(default_factory=tuple, compare=False)
    kwargs: Dict[str, Any] = field(default_factory=dict, compare=False)
    done_event: threading.Event = field(default_factory=threading.Event, compare=False)
    result: Any = field(default=None, compare=False)
    error: Optional[Exception] = field(default=None, compare=False)

class GPUInferenceQueue:
    _instance: Optional["GPUInferenceQueue"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._queue = []
        self._queue_lock = threading.Lock()
        self._condition = threading.Condition(self._queue_lock)
        self._gpu_semaphore = threading.Semaphore(1)  # Strictly serialize GPU generations
        self._active_worker = True
        self._request_counter = 0

        # Performance & telemetry metrics
        self.stats = {
            "total_requests": 0,
            "completed_requests": 0,
            "failed_requests": 0,
            "total_wait_time_sec": 0.0,
            "total_execution_time_sec": 0.0,
            "vram_limit_mb": 6144,
            "current_vram_used_mb": 0,
            "last_latency_sec": 0.0
        }

        # Background worker daemon
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True, name="JarvisInferenceWorker")
        self._worker_thread.start()

    def get_vram_status(self) -> Dict[str, Any]:
        """Queries local nvidia-smi for current VRAM utilization."""
        try:
            cmd = ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,nounits,noheader"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=3.0)
            if res.returncode == 0:
                parts = res.stdout.strip().split(",")
                if len(parts) >= 3:
                    used = float(parts[0].strip())
                    total = float(parts[1].strip())
                    gpu_util = float(parts[2].strip())
                    self.stats["current_vram_used_mb"] = used
                    return {
                        "used_mb": used,
                        "total_mb": total,
                        "free_mb": max(0.0, total - used),
                        "gpu_util_pct": gpu_util,
                        "headroom_pct": round(((total - used) / total) * 100, 1)
                    }
        except Exception:
            pass
        return {
            "used_mb": self.stats["current_vram_used_mb"],
            "total_mb": self.stats["vram_limit_mb"],
            "free_mb": max(0.0, self.stats["vram_limit_mb"] - self.stats["current_vram_used_mb"]),
            "headroom_pct": 28.5
        }

    def execute_inference(
        self,
        func: Callable[..., Any],
        *args,
        priority: InferencePriority = InferencePriority.ORCHESTRATION,
        timeout: Optional[float] = 180.0,
        **kwargs
    ) -> Any:
        """
        Submits an inference callable to the priority queue, blocks until completion,
        and returns the result or raises any encountered exception.
        """
        with self._queue_lock:
            self._request_counter += 1
            req_id = f"req-{self._request_counter}-{int(time.time()*1000)}"
            item = QueuedInferenceRequest(
                priority=int(priority),
                timestamp=time.time(),
                request_id=req_id,
                func=func,
                args=args,
                kwargs=kwargs
            )
            heapq.heappush(self._queue, item)
            self.stats["total_requests"] += 1
            self._condition.notify()

        # Wait for completion
        start_wait = time.time()
        completed = item.done_event.wait(timeout=timeout)
        if not completed:
            raise TimeoutError(f"Inference request {req_id} timed out after {timeout}s waiting in queue.")

        wait_duration = item.timestamp - start_wait
        self.stats["total_wait_time_sec"] += max(0.0, wait_duration)

        if item.error:
            self.stats["failed_requests"] += 1
            raise item.error

        self.stats["completed_requests"] += 1
        return item.result

    def _process_queue(self):
        """Worker loop that dispatches requests one by one to protect GPU VRAM."""
        while self._active_worker:
            req: Optional[QueuedInferenceRequest] = None
            with self._condition:
                while not self._queue and self._active_worker:
                    self._condition.wait(timeout=1.0)
                if not self._active_worker:
                    break
                if self._queue:
                    req = heapq.heappop(self._queue)

            if req is None:
                continue

            # Execute with single-slot GPU lock
            with self._gpu_semaphore:
                t0 = time.time()
                try:
                    req.result = req.func(*req.args, **req.kwargs)
                except Exception as ex:
                    req.error = ex
                finally:
                    duration = time.time() - t0
                    self.stats["last_latency_sec"] = duration
                    self.stats["total_execution_time_sec"] += duration
                    req.done_event.set()

    def get_queue_health(self) -> Dict[str, Any]:
        with self._queue_lock:
            pending_count = len(self._queue)
        vram = self.get_vram_status()
        avg_latency = 0.0
        if self.stats["completed_requests"] > 0:
            avg_latency = round(self.stats["total_execution_time_sec"] / self.stats["completed_requests"], 3)

        return {
            "pending_requests_in_queue": pending_count,
            "total_requests": self.stats["total_requests"],
            "completed_requests": self.stats["completed_requests"],
            "failed_requests": self.stats["failed_requests"],
            "avg_latency_sec": avg_latency,
            "last_latency_sec": round(self.stats["last_latency_sec"], 3),
            "vram_status": vram
        }

# Global singleton
inference_queue = GPUInferenceQueue()
