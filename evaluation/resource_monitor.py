"""
Resource Monitoring Engine for Operation Jarvis.
Tracks CPU, RAM, and NVIDIA RTX 4050 GPU VRAM usage.
"""
import shutil
import subprocess
import psutil
from typing import Dict, Any

class ResourceMonitor:
    def __init__(self):
        self.has_nvidia_smi = shutil.which("nvidia-smi") is not None

    def sample_gpu(self) -> Dict[str, Any]:
        if not self.has_nvidia_smi:
            return {"gpu_available": False}

        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits"
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            if proc.returncode == 0 and proc.stdout.strip():
                parts = [p.strip() for p in proc.stdout.strip().split(",")]
                if len(parts) >= 6:
                    return {
                        "gpu_available": True,
                        "gpu_name": parts[0],
                        "vram_total_mb": float(parts[1]),
                        "vram_used_mb": float(parts[2]),
                        "vram_free_mb": float(parts[3]),
                        "gpu_util_percent": float(parts[4]),
                        "gpu_temp_c": float(parts[5])
                    }
        except Exception:
            pass
        return {"gpu_available": False}

    def sample_system(self) -> Dict[str, Any]:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        gpu = self.sample_gpu()

        return {
            "cpu_percent": cpu,
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_used_gb": round((mem.total - mem.available) / (1024**3), 2),
            "ram_percent": mem.percent,
            "gpu": gpu
        }

resource_monitor = ResourceMonitor()
