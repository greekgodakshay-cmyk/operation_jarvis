"""
Authoritative Host OS Temporal Awareness Module for Operation JARVIS.
Provides deterministic, sub-millisecond host clock information, timezone awareness,
and automated prompt injection to prevent temporal hallucination.
"""
import time
from datetime import datetime, timezone
from typing import Any, Dict

def get_system_temporal_info() -> Dict[str, Any]:
    """Retrieves authoritative local and UTC clock readings from host OS."""
    now_local = datetime.now()
    now_utc = datetime.now(timezone.utc)
    
    # Calculate local offset from UTC
    local_tz = now_local.astimezone().tzinfo
    tz_name = time.tzname[time.daylight] if time.daylight else time.tzname[0]
    
    offset = now_local.astimezone().utcoffset()
    total_seconds = int(offset.total_seconds()) if offset else 0
    sign = "+" if total_seconds >= 0 else "-"
    hours = abs(total_seconds) // 3600
    minutes = (abs(total_seconds) % 3600) // 60
    offset_str = f"UTC{sign}{hours:02d}:{minutes:02d}"

    return {
        "timestamp_epoch": time.time(),
        "local_iso": now_local.isoformat(),
        "utc_iso": now_utc.isoformat(),
        "date": now_local.strftime("%Y-%m-%d"),
        "time": now_local.strftime("%H:%M:%S"),
        "weekday": now_local.strftime("%A"),
        "timezone_name": tz_name,
        "utc_offset": offset_str,
        "formatted_authoritative": f"{now_local.strftime('%Y-%m-%d %H:%M:%S')} {tz_name} ({offset_str}), {now_local.strftime('%A')}"
    }

def get_temporal_context_prompt() -> str:
    """Returns authoritative system context snippet to prepend or inject into LLM prompts."""
    info = get_system_temporal_info()
    return (
        f"[AUTHORITATIVE HOST CLOCK: Current Date & Time is {info['formatted_authoritative']}. "
        f"All temporal references (today, yesterday, tomorrow, current year, recent events) must anchor to this host timestamp.]"
    )

def tool_get_current_time() -> Dict[str, Any]:
    """
    Registered tool: Returns authoritative host OS date, time, and timezone in sub-millisecond latency.
    Zero LLM hallucination, purely deterministic.
    """
    t0 = time.perf_counter()
    info = get_system_temporal_info()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    
    return {
        "ok": True,
        "current_date": info["date"],
        "current_time": info["time"],
        "weekday": info["weekday"],
        "timezone": info["timezone_name"],
        "utc_offset": info["utc_offset"],
        "iso_timestamp": info["local_iso"],
        "formatted": info["formatted_authoritative"],
        "latency_ms": round(elapsed_ms, 3)
    }
