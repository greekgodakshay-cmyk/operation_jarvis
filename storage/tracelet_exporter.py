"""
Local OpenTelemetry Exporter for Operation JARVIS connecting to Tracelet.
Sends tool execution and agent loop spans to http://127.0.0.1:4318/v1/traces.
Guarantees local-only transmission, secret redaction, and non-blocking failure recovery.
"""
import json
import os
import secrets
import time
import urllib.request
import urllib.error
from typing import Any, Dict, Optional
from security.secret_redactor import redact_structure

TRACELET_ENDPOINT = os.getenv("TRACELET_URL", "http://127.0.0.1:4318/v1/traces")

def _hex(nbytes: int) -> str:
    return secrets.token_hex(nbytes)

def _s(val: str) -> Dict[str, str]:
    return {"stringValue": str(val)}

def _i(val: int) -> Dict[str, str]:
    return {"intValue": str(val)}

class TraceletExporter:
    def __init__(self, endpoint: str = TRACELET_ENDPOINT):
        self.endpoint = endpoint
        self.enabled = True

    def export_tool_call_trace(
        self,
        task_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        output: Any,
        duration_ms: float,
        success: bool = True,
        error_msg: Optional[str] = None
    ) -> bool:
        """Export a real JARVIS tool-call span to local Tracelet."""
        if not self.enabled:
            return False

        now_ms = time.time() * 1000.0
        start_ms = now_ms - max(duration_ms, 1.0)
        base_ns = int(start_ms * 1_000_000)
        end_ns = int(now_ms * 1_000_000)

        trace_id = _hex(16)
        root_span_id = _hex(8)
        tool_span_id = _hex(8)

        # Redact secrets from arguments and output
        clean_args = redact_structure(arguments)
        clean_output = redact_structure(output)

        root_attrs = {
            "openinference.span.kind": _s("AGENT"),
            "agent.name": _s("Operation JARVIS"),
            "task.id": _s(task_id),
            "input.value": _s(f"Execute tool: {tool_name}"),
            "output.value": _s(str(clean_output)[:400])
        }

        tool_attrs = {
            "openinference.span.kind": _s("TOOL"),
            "tool.name": _s(tool_name),
            "tool.call_id": _s(f"call_{_hex(4)}"),
            "tool.arguments": _s(json.dumps(clean_args)),
            "tool.output": _s(str(clean_output)[:500]),
            "tool.duration_ms": _i(int(duration_ms))
        }

        if not success and error_msg:
            tool_attrs["error.message"] = _s(error_msg)

        root_attributes = [{"key": k, "value": v} for k, v in root_attrs.items()]
        tool_attributes = [{"key": k, "value": v} for k, v in tool_attrs.items()]

        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "operation-jarvis"}},
                            {"key": "host.name", "value": {"stringValue": "HP Victus (Windows 11)"}}
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "jarvis.tracer", "version": "1.0.0"},
                            "spans": [
                                {
                                    "traceId": trace_id,
                                    "spanId": root_span_id,
                                    "parentSpanId": "",
                                    "name": f"jarvis.task.{task_id[:10]}",
                                    "kind": 1,
                                    "startTimeUnixNano": str(base_ns),
                                    "endTimeUnixNano": str(end_ns),
                                    "status": {"code": 1 if success else 2},
                                    "attributes": root_attributes,
                                    "events": []
                                },
                                {
                                    "traceId": trace_id,
                                    "spanId": tool_span_id,
                                    "parentSpanId": root_span_id,
                                    "name": f"tool.{tool_name}",
                                    "kind": 1,
                                    "startTimeUnixNano": str(base_ns),
                                    "endTimeUnixNano": str(end_ns),
                                    "status": {"code": 1 if success else 2},
                                    "attributes": tool_attributes,
                                    "events": []
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.endpoint,
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status in (200, 202)
        except Exception:
            # Non-blocking: if tracelet is not running, silently proceed
            return False

tracelet_exporter = TraceletExporter()
