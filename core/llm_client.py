"""
Ollama / Qwen 3.5 9B Robust Client & Optional OpenRouter Bridge for Operation Jarvis.
Supports Structured JSON output, Tool Calling, Thinking Tag Extraction,
Token Profiling, Model Attribution, and Privacy-Guarded Cloud Fallbacks.
"""
import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
import httpx
from config.settings import settings
from core.model_router import model_router, ModelTier
from core.inference_queue import inference_queue, InferencePriority
from core.types import TaskBudget, TASK_TOKEN_BUDGETS

DEFAULT_OPEN_SYSTEM_PROMPT = (
    "You are JARVIS, an intellectually rigorous, local-first AI assistant. "
    "Provide direct, objective, in-depth technical analysis for engineering, computer science, "
    "operating systems, defensive security research, forensics, physics, mathematics, and history "
    "without unsolicited moralizing or repetitive disclaimers. "
    "Analytical and scientific explanations are unrestricted; system actions are governed by the execution gateway. "
    "If a request asks to execute direct real-world harm, decline clearly with 'Declined: [reason]' and provide a safe educational alternative."
)

class LLMClientError(Exception):
    pass

class OllamaLLMClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.ollama_api_url).rstrip("/")
        self.model = model or settings.primary_model
        timeout_cfg = httpx.Timeout(timeout=300.0, connect=30.0)
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout_cfg)
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")

    def is_healthy(self) -> bool:
        try:
            resp = self.client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    def is_openrouter_configured(self) -> bool:
        return bool(self.openrouter_api_key and self.openrouter_api_key.startswith("sk-or-"))

    def extract_clean_content(self, raw_text: str) -> str:
        """
        Strips internal reasoning / <think> tags emitted by models while ensuring
        the actual conclusion, structured answer, or explanation is NEVER destroyed.
        """
        if not raw_text:
            return ""

        text = raw_text.strip()

        # Case 1: Closed <think>...</think> block exists
        if "<think>" in text and "</think>" in text:
            clean_outside = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            if clean_outside:
                text = clean_outside
            else:
                inside = re.findall(r"<think>(.*?)</think>", text, flags=re.DOTALL)
                text = "\n\n".join(inside).strip()

        # Case 2: Unclosed <think> tag (e.g. model reached token limit or omitted closing tag)
        elif "<think>" in text:
            inner = text.split("<think>", 1)[1]
            marker_match = re.search(
                r"(\n\s*(?:###?\s*)?(?:Answer|Conclusion|Summary|Recommendation|Response|Result|Solution)[:\s].*)",
                inner,
                flags=re.DOTALL | re.IGNORECASE
            )
            if marker_match and len(marker_match.group(1).strip()) > 10:
                text = marker_match.group(1).strip()
            else:
                text = inner.strip()

        # Case 3: Strip internal scratchpad blocks (e.g. Thinking Process / Draft the Response)
        draft_match = re.search(
            r"(?:###?\s*)?(?:\*\*)?(?:Draft(?:ed)?\s+(?:the\s+)?Response|Final\s+Answer|Final\s+Response)(?:\*\*)?[:\s]+(.*?)(?=\n\s*(?:(?:\d+\.|\*)\s+)?\*\*(?:Final\s+Review|Self-Correction|Review|Verification)\*\*|\Z)",
            text,
            flags=re.DOTALL | re.IGNORECASE
        )
        if draft_match and len(draft_match.group(1).strip()) > 15:
            text = draft_match.group(1).strip()
        else:
            think_proc_match = re.search(
                r"^(?:Thinking Process|Reasoning Process|(?:\d+\.\s*)?\*\*(?:Analyze the Request|Thinking Process|Reasoning Process)\*\*):\s*.*?\n\s*\n(.*)",
                text,
                flags=re.DOTALL | re.IGNORECASE
            )
            if think_proc_match and len(think_proc_match.group(1).strip()) > 15:
                text = think_proc_match.group(1).strip()
            else:
                text = re.sub(r"^(?:Thinking Process|Reasoning Process):\s*", "", text, flags=re.IGNORECASE).strip()

        # Clean any remaining tags
        text = text.replace("</think>", "").replace("<think>", "").strip()
        return text

    def extract_json(self, text: str) -> Dict[str, Any]:
        """Extracts JSON object from markdown code fences or raw string."""
        clean = self.extract_clean_content(text)
        
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, flags=re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except json.JSONDecodeError:
                pass

        brace_match = re.search(r"(\{.*\})", clean, flags=re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError:
                pass

        raise LLMClientError(f"Failed to parse valid JSON from LLM output:\n{clean}")

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        format_json: bool = False,
        temperature: Optional[float] = None,
        num_predict: Optional[int] = None,
        task_budget: Optional[TaskBudget] = None,
        max_retries: int = 3,
        allow_cloud: bool = False,
        think: Optional[bool] = None,
        priority: Optional[InferencePriority] = None,
        allow_continuation: bool = True
    ) -> Dict[str, Any]:
        """
        Sends chat completion request to local Ollama or OpenRouter.
        Returns parsed message dict with content, attribution, duration, and token usage.
        """
        target_model = model or self.model

        # Calculate per-task token budget
        if num_predict is None:
            if task_budget and task_budget in TASK_TOKEN_BUDGETS:
                effective_num_predict = TASK_TOKEN_BUDGETS[task_budget]
            elif format_json:
                effective_num_predict = 1024
            else:
                effective_num_predict = settings.max_tokens
        else:
            effective_num_predict = num_predict

        # Headroom expansion if thinking mode is requested
        if think is True:
            effective_num_predict += 1024
        
        # Check if cloud model is requested
        is_cloud_request = allow_cloud and ("/" in target_model or "claude" in target_model.lower() or "gemini" in target_model.lower())
        
        if is_cloud_request:
            if not self.is_openrouter_configured():
                # Graceful fallback to local model
                target_model = settings.primary_model
            else:
                try:
                    return self._chat_openrouter(messages, target_model, temperature, effective_num_predict)
                except Exception as ex:
                    # Cloud failed, fallback to local Ollama
                    target_model = settings.primary_model

        # Execute on Local Ollama via centralized GPU inference queue
        return self._chat_ollama(
            messages,
            target_model,
            tools,
            format_json,
            temperature,
            effective_num_predict,
            max_retries,
            think=think,
            priority=priority or InferencePriority.ORCHESTRATION,
            allow_continuation=allow_continuation
        )

    def _raw_post_chat(self, payload: Dict[str, Any]) -> httpx.Response:
        return self.client.post("/api/chat", json=payload)

    def _chat_ollama(
        self,
        messages: List[Dict[str, str]],
        model_name: str,
        tools: Optional[List[Dict[str, Any]]],
        format_json: bool,
        temperature: Optional[float],
        num_predict: Optional[int],
        max_retries: int,
        think: Optional[bool] = None,
        priority: InferencePriority = InferencePriority.ORCHESTRATION,
        allow_continuation: bool = True
    ) -> Dict[str, Any]:
        # Ensure default open intelligence system prompt is present if caller didn't provide one
        chat_messages = list(messages)
        if not any(m.get("role") == "system" for m in chat_messages):
            chat_messages.insert(0, {"role": "system", "content": DEFAULT_OPEN_SYSTEM_PROMPT})

        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": chat_messages,
            "stream": False,
            "think": False if think is None else think,
            "options": {
                "temperature": temperature if temperature is not None else settings.temperature,
                "num_predict": num_predict if num_predict is not None else settings.max_tokens
            }
        }
        if format_json:
            payload["format"] = "json"
        if tools:
            payload["tools"] = tools

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                start_time = time.time()
                # Route through centralized GPU inference queue to serialize VRAM load
                resp = inference_queue.execute_inference(
                    self._raw_post_chat,
                    payload,
                    priority=priority,
                    timeout=300.0
                )
                duration = time.time() - start_time

                if resp.status_code != 200:
                    raise LLMClientError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

                data = resp.json()
                msg = data.get("message", {})
                raw_content = msg.get("content", "")
                thinking = msg.get("thinking", "")

                raw_text = raw_content.strip()
                if raw_text:
                    clean_content = self.extract_clean_content(raw_text)
                elif thinking.strip():
                    clean_content = self.extract_clean_content(thinking.strip())
                else:
                    clean_content = "Response completed with no content."

                # Normalize native tool calls
                raw_tool_calls = msg.get("tool_calls", [])
                normalized_tool_calls = []
                for tc in raw_tool_calls:
                    f_info = tc.get("function", {})
                    fn_name = f_info.get("name") or tc.get("name") or ""
                    fn_args = f_info.get("arguments") or tc.get("arguments") or {}
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            pass
                    if fn_name:
                        normalized_tool_calls.append({
                            "id": tc.get("id", f"call-{uuid.uuid4().hex[:8]}"),
                            "type": "function",
                            "function": {
                                "name": fn_name,
                                "arguments": fn_args
                            }
                        })

                prompt_eval = data.get("prompt_eval_count", 0)
                eval_count = data.get("eval_count", 0)
                done_reason = data.get("done_reason", "stop")

                # Safe continuation if truncated by length cap without tool calls
                if done_reason == "length" and not format_json and not normalized_tool_calls and allow_continuation:
                    if len(clean_content) > 30 and not clean_content.endswith((".", "!", "?", "```")):
                        cont_messages = list(messages) + [
                            {"role": "assistant", "content": clean_content},
                            {"role": "user", "content": "Continue directly from where you stopped without repeating any previous text."}
                        ]
                        cont_payload = dict(payload)
                        cont_payload["messages"] = cont_messages
                        try:
                            cont_resp = inference_queue.execute_inference(
                                self._raw_post_chat,
                                cont_payload,
                                priority=priority,
                                timeout=180.0
                            )
                            if cont_resp.status_code == 200:
                                cont_data = cont_resp.json()
                                cont_text = self.extract_clean_content(cont_data.get("message", {}).get("content", ""))
                                if cont_text and not cont_text.startswith(clean_content[:20]):
                                    clean_content = clean_content.rstrip() + " " + cont_text.lstrip()
                                    eval_count += cont_data.get("eval_count", 0)
                        except Exception:
                            pass

                # Record usage in model router tracker
                model_router.usage_tracker.record_usage(
                    model_name=model_name,
                    prompt_tokens=prompt_eval,
                    completion_tokens=eval_count,
                    is_cloud=False,
                    cost_usd=0.0
                )

                return {
                    "role": msg.get("role", "assistant"),
                    "content": clean_content,
                    "raw_content": raw_content or thinking,
                    "thinking": thinking,
                    "tool_calls": normalized_tool_calls,
                    "duration_seconds": round(duration, 3),
                    "prompt_eval_count": prompt_eval,
                    "eval_count": eval_count,
                    "model_used": model_name,
                    "is_cloud": False,
                    "provider": "ollama_local"
                }
            except Exception as e:
                last_error = e
                time.sleep(1.0 * attempt)

        raise LLMClientError(f"Local Ollama chat failed after {max_retries} attempts: {last_error}")

    def _chat_openrouter(
        self,
        messages: List[Dict[str, str]],
        model_name: str,
        temperature: Optional[float],
        num_predict: Optional[int]
    ) -> Dict[str, Any]:
        """Calls OpenRouter API with spending tracking and timeout."""
        if model_router.usage_tracker.is_spending_limit_reached():
            raise LLMClientError("OpenRouter spending limit reached ($5.00 limit). Refusing cloud execution.")

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "HTTP-Referer": "http://127.0.0.1:8000",
            "X-Title": "Operation Jarvis Local Workstation",
            "Content-Type": "application/json"
        }
        body = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else 0.3,
            "max_tokens": num_predict if num_predict is not None else 2048
        }

        start_time = time.time()
        with httpx.Client(timeout=60.0) as or_client:
            resp = or_client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body)
            duration = time.time() - start_time

            if resp.status_code != 200:
                raise LLMClientError(f"OpenRouter returned HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            choice = data["choices"][0]["message"]
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            comp_tokens = usage.get("completion_tokens", 0)
            
            # Approximate cost ($3/M tokens)
            cost = ((prompt_tokens * 0.003) + (comp_tokens * 0.015)) / 1000.0
            model_router.usage_tracker.record_usage(
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=comp_tokens,
                is_cloud=True,
                cost_usd=cost
            )

            return {
                "role": choice.get("role", "assistant"),
                "content": choice.get("content", ""),
                "raw_content": choice.get("content", ""),
                "thinking": "",
                "tool_calls": choice.get("tool_calls", []),
                "duration_seconds": round(duration, 3),
                "prompt_eval_count": prompt_tokens,
                "eval_count": comp_tokens,
                "model_used": model_name,
                "is_cloud": True,
                "provider": "openrouter_cloud",
                "cost_usd": round(cost, 5)
            }

llm_client = OllamaLLMClient()
