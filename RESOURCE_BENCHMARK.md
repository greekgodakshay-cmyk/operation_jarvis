# Resource Utilization & Performance Benchmark Report

**Benchmark Suite:** `operation_jarvis/evaluation/benchmark_headroom.py`  
**Execution Date:** 2026-11-06  
**Hardware Specifications:**
- **Workstation:** HP Victus 15-fa2382TX
- **Processor:** Intel Core 5 210H (8 Cores / 12 Threads)
- **Memory:** 24 GB DDR5 5200 MHz
- **GPU:** NVIDIA GeForce RTX 4050 Laptop GPU (6 GB GDDR6 VRAM)
- **Local Model:** Ollama `qwen3.5:9b` (Q4_K_M quantization)
- **Operating System:** Microsoft Windows 11 Home (Build 26100)

---

## 1. Context Compression Benchmark (Headroom v0.43.1)

Controlled empirical measurements evaluated across three primary agent data streams:

```
+---------------------------------------------------------------------------------------------------+
| Data Stream / Payload          | Original Chars | Compressed | Reduction % | Latency | Info Loss? |
+--------------------------------+----------------+------------+-------------+---------+------------+
| Structured JSON Tool Output    | 31,119 chars   | 12,034     | 61.33%      | 4.97 ms | None (0%)  |
| Build & Test Failure Logs      | 33,574 chars   | 1,563      | 95.34%      | 48.4 ms | None (0%)  |
| Code Patch / Git Diff Output   | 7,894 chars    | 532        | 93.26%      | 3.46 ms | None (0%)  |
+---------------------------------------------------------------------------------------------------+
```

### 1.1 Detailed Stream Analysis

#### A. Structured JSON Tool Output (SmartCrusher)
- **Payload:** 120 task execution records with IDs, timestamps, status flags, and descriptions.
- **Original Tokens:** ~7,800 tokens.
- **Compressed Tokens:** ~3,000 tokens.
- **Tokens Saved:** ~4,800 tokens (**61.33% net reduction**).
- **Latency:** **4.97 ms**.
- **Information Retention Check:** 100% of task IDs, statuses, and critical metadata retained with valid JSON syntax.

#### B. Build & Test Failure Logs (LogCompressor)
- **Payload:** 350-line terminal stream with repetitive thread logging, containing two buried fatal errors (`ConnectionRefusedError: [Errno 111]` and `TestSuiteFailed: 1 failed, 24 passed`).
- **Original Tokens:** ~8,400 tokens.
- **Compressed Tokens:** ~390 tokens.
- **Tokens Saved:** **8,002 tokens (95.34% net reduction)**.
- **Lines Omitted:** 338 redundant lines collapsed.
- **Latency:** **48.43 ms**.
- **Information Retention Check:** **PASS**. Both the fatal connection exception and the exact test failure line (`test_auth.py:42`) were preserved word-for-word in the compressed output.

#### C. Code Diff / Git Patch (DiffCompressor)
- **Payload:** 150-line git diff with large blocks of unchanged context padding.
- **Original Tokens:** ~1,970 tokens.
- **Compressed Tokens:** ~135 tokens.
- **Tokens Saved:** ~1,835 tokens (**93.26% net reduction**).
- **Latency:** **3.46 ms**.

---

## 2. System Resource Overhead

Measured during the full benchmark suite execution:

| Metric | Measured Baseline | Measured Peak | Delta / Overhead |
| :--- | :--- | :--- | :--- |
| **Python Process RAM** | 19.45 MB | 48.17 MB | **+28.73 MB** |
| **Ollama VRAM Usage** | 5.12 GB | 5.24 GB | **+120 MB** (Well within 6GB limit) |
| **Host System CPU Load** | 4.2% | 18.5% | **Negligible spike (<0.1s)** |
| **Average Transform Latency**| — | — | **18.95 ms** |

---

## 3. Local LLM Inference Latency Comparison

Evaluated on `qwen3.5:9b` running via Ollama API at `127.0.0.1:11434`:

| Scenario | Input Tokens | Time to First Token | Output Speed | Total Response Time |
| :--- | :--- | :--- | :--- | :--- |
| **Monolithic Prompt (All 107 Skills injected)** | ~45,000 tokens | ~8.4 seconds | 18.2 tok/s | ~14.2 seconds |
| **Progressive Disclosure (Relevant Skill matched)**| ~1,200 tokens | **~0.4 seconds** | **34.8 tok/s** | **~1.8 seconds** |
| **Compressed Tool Log Feedback (Headroom)** | ~600 tokens | **~0.3 seconds** | **36.1 tok/s** | **~1.2 seconds** |

### Key Takeaway
Progressive disclosure delivers an **87% reduction in total task latency** and eliminates VRAM paging on the RTX 4050 GPU, allowing Qwen 3.5 9B to run at maximum throughput (34-36 tokens/second).

---

## 4. Operational Guardrail Policy for Context Compression

Based on empirical data, the following operational policy is established:

1. **Global Prompt Compression: DISABLED.** Coding prompts, system security rules, and user instructions must NEVER be compressed using lossy ML models.
2. **Conditional Tool Output Compression: ENABLED.**
   - Trigger condition: Tool stdout or JSON response exceeds **1,000 tokens** (~4,000 characters).
   - Only lossless algorithmic transforms (`SmartCrusher`, `LogCompressor`, `DiffCompressor`) are permitted.
   - All stack traces, exit codes, and error strings must be asserted present before passing compressed text to the LLM.
