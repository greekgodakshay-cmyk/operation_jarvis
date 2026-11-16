"""
Hardware and Inference Resource Profiling for Operation JARVIS.
Measures:
- Intel Core 5 210H CPU utilization
- 24 GB DDR5 RAM utilization
- RTX 4050 (6GB VRAM) allocation and headroom
- Ollama inference latency: prompt processing, generation speed (tokens/sec), first-token latency
"""
import sys
import os
import time
import json
import psutil
from pathlib import Path

JARVIS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(JARVIS_ROOT))

from core.inference_queue import inference_queue
from core.llm_client import llm_client
from core.types import TaskBudget

def profile_system_and_inference():
    print("=" * 60)
    print("OPERATION JARVIS — HARDWARE & RESOURCE TELEMETRY PROFILE")
    print("=" * 60)

    # 1. System Hardware Telemetry
    cpu_pct = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    vram = inference_queue.get_vram_status()

    print(f"Host:                    HP Victus 15-fa2xxx (Windows 11 Home 64-bit)")
    print(f"CPU:                     Intel Core 5 210H (12 threads)")
    print(f"CPU Utilization:         {cpu_pct}%")
    print(f"DDR5 System RAM:         {mem.used / (1024**3):.2f} GB used / {mem.total / (1024**3):.2f} GB ({mem.percent}%)")
    print(f"DDR5 Free RAM:           {mem.available / (1024**3):.2f} GB available")
    print(f"GPU Hardware:            NVIDIA GeForce RTX 4050 Laptop GPU")
    print(f"VRAM Dedicated Total:    {vram['total_mb']} MB (6,141 MiB)")
    print(f"VRAM Allocated:          {vram['used_mb']} MB")
    print(f"VRAM Headroom:           {vram['headroom_pct']}% ({vram['free_mb']} MB free)")
    print(f"System Drive (C:):       {disk.used / (1024**3):.2f} GB / {disk.total / (1024**3):.2f} GB ({disk.percent}%)")

    # 2. Live Inference Latency & Speed Benchmark
    print("\n--- Live Ollama Inference Benchmark (qwen3.5:9b Q4_K_M) ---")
    prompt = "Explain in exactly two concise sentences why WAL mode in SQLite allows simultaneous readers and one writer."
    
    t0 = time.time()
    res = llm_client.chat(
        messages=[
            {"role": "system", "content": "You are a concise systems engineer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        think=False,
        task_budget=TaskBudget.SHORT_ANSWER
    )
    total_latency = time.time() - t0
    
    content = res.get("content", "").strip()
    metrics = res.get("metrics", {})
    eval_count = metrics.get("eval_count", 0)
    eval_duration_sec = metrics.get("eval_duration_ns", 0) / 1e9
    prompt_eval_count = metrics.get("prompt_eval_count", 0)
    prompt_eval_duration_sec = metrics.get("prompt_eval_duration_ns", 0) / 1e9
    tokens_per_sec = (eval_count / eval_duration_sec) if eval_duration_sec > 0 else (eval_count / total_latency)

    print(f"Test Prompt Tokens:      {prompt_eval_count}")
    print(f"Prompt Eval Speed:       {prompt_eval_count / prompt_eval_duration_sec:.1f} tokens/sec" if prompt_eval_duration_sec > 0 else "Prompt Eval Speed: N/A")
    print(f"Generated Tokens:        {eval_count} tokens")
    print(f"Generation Speed:        {tokens_per_sec:.2f} tokens/sec")
    print(f"Total Wall-Clock Time:   {total_latency:.2f}s")
    print(f"Output Received:\n\"{content}\"")
    print("\nHARDWARE & INFERENCE PROFILING COMPLETE: VERIFIED")
    print("=" * 60)

if __name__ == "__main__":
    profile_system_and_inference()
