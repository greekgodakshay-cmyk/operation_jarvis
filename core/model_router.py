"""
Model Routing and Tier Classification Engine for Operation JARVIS.
Directs tasks to Local Qwen models (qwen-batman:latest, qwen-text:latest, qwen3.5:9b)
by default for zero-cost, private execution, and provides policy-governed escalation
to OpenRouter / Antigravity Cloud with privacy boundaries and budget limits.
"""
import enum
import os
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ModelTier(str, enum.Enum):
    LOCAL_QWEN_BATMAN = "local_qwen_batman"
    LOCAL_QWEN_TEXT = "local_qwen_text"
    LOCAL_QWEN = "local_qwen_3.5_9b"
    OPENROUTER_CLOUD = "openrouter_cloud"
    ANTIGRAVITY_CLOUD = "antigravity_orchestrator"

class RoutingDecision(BaseModel):
    selected_tier: ModelTier
    model_name: str
    is_cloud: bool
    confidence: float
    reason: str
    task_classification: str
    requires_external_research: bool
    privacy_blocked_cloud: bool = False
    estimated_cost_usd: float = 0.0

class UsageTracker:
    """Tracks token consumption and spending for local and cloud models."""
    def __init__(self, spending_limit_usd: float = 5.0):
        self.spending_limit_usd = spending_limit_usd
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.model_counts: Dict[str, int] = {}

    def record_usage(self, model_name: str, prompt_tokens: int, completion_tokens: int, is_cloud: bool = False, cost_usd: float = 0.0):
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cost_usd += cost_usd
        self.model_counts[model_name] = self.model_counts.get(model_name, 0) + 1

    def is_spending_limit_reached(self) -> bool:
        return self.total_cost_usd >= self.spending_limit_usd

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "spending_limit_usd": self.spending_limit_usd,
            "spending_limit_reached": self.is_spending_limit_reached(),
            "model_invocations": self.model_counts
        }

class ModelRouter:
    """
    Intelligent router analyzing user objective complexity, privacy requirements,
    and computational needs across local Ollama models and cloud providers.
    """
    # Batman personal workstation indicators
    BATMAN_INDICATORS = [
        r"\b(batman|workstation|my workstation|my projects|internship|backup|studenttracker|victus|laptop|preference)\b",
        r"\b(who am i|who are you|remember me|my setup)\b"
    ]

    # Deep text reasoning & analysis suited for qwen-text
    TEXT_ANALYSIS_INDICATORS = [
        r"\b(deep dive|explain theoretical|first principles|mathematical proof|algorithm analysis)\b",
        r"\b(malware architecture|reverse engineering|forensics|criminal psychology|exploit analysis)\b",
        r"\b(essay|comprehensive critique|philosophy|historical analysis|whitepaper)\b",
        r"\b(technical review|code analysis without execution|explain concept)\b"
    ]

    # Tasks that may warrant cloud-tier escalation
    COMPLEX_CLOUD_INDICATORS = [
        r"\b(full architecture|multi-repo|cross-cloud|cloud migration|terraform infrastructure)\b",
        r"\b(deep adversarial red-teaming|complex formal verification)\b",
        r"\b(million token context|massive codebase re-architecture)\b"
    ]

    # Research indicators requiring live internet
    RESEARCH_INDICATORS = [
        r"\b(latest|current|today|this week|recent|news|announcement)\b",
        r"\b(cve|vulnerability|zero-day|advisory|patch)\b",
        r"\b(paper|arxiv|research|breakthrough|release)\b",
        r"\b(compare current|what's happening in)\b"
    ]

    # Privacy markers: never send to cloud without explicit authorization
    PRIVACY_MARKERS = [
        r"\b(password|secret|credential|api[_-]key|token|id_rsa|private_key)\b",
        r"\b(local_ai_memory|studenttracker|multi-cloud-backup)\b",
        r"C:\\Users\\[^\\]+",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"  # email addresses
    ]

    def __init__(self):
        self.usage_tracker = UsageTracker()

    def check_privacy_boundary(self, text: str) -> bool:
        """Returns True if sensitive local data or private markers are detected."""
        lower = text.lower()
        return any(re.search(pat, lower) for pat in self.PRIVACY_MARKERS)

    def route_task(
        self,
        objective: str,
        prefer_local: bool = True,
        allow_cloud_privacy: bool = False,
        requested_provider: Optional[str] = None
    ) -> RoutingDecision:
        cleaned = objective.strip()
        lower = cleaned.lower()

        # Check research requirement
        needs_research = any(re.search(pat, lower) for pat in self.RESEARCH_INDICATORS)

        # Check privacy boundary
        has_private_data = self.check_privacy_boundary(cleaned)

        # 1. Check for OpenRouter explicit request
        if requested_provider == "openrouter" or (not prefer_local and not self.usage_tracker.is_spending_limit_reached()):
            if has_private_data and not allow_cloud_privacy:
                # Privacy block: enforce local fallback
                return RoutingDecision(
                    selected_tier=ModelTier.LOCAL_QWEN_TEXT,
                    model_name="qwen-text:latest",
                    is_cloud=False,
                    confidence=0.95,
                    reason="Cloud requested, but objective contains private memory/credentials. Enforced local fallback under privacy boundary policy.",
                    task_classification="Privacy-Guarded Text Reasoning",
                    requires_external_research=needs_research,
                    privacy_blocked_cloud=True
                )
            
            # Cloud tier authorized
            openrouter_model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
            return RoutingDecision(
                selected_tier=ModelTier.OPENROUTER_CLOUD,
                model_name=openrouter_model,
                is_cloud=True,
                confidence=0.90,
                reason="Task routed to OpenRouter cloud provider as requested; privacy verified.",
                task_classification="Cloud Augmented Reasoning",
                requires_external_research=needs_research,
                estimated_cost_usd=0.003
            )

        # 2. Check for explicit complex cloud requirements
        has_cloud_indicator = any(re.search(pat, lower) for pat in self.COMPLEX_CLOUD_INDICATORS)
        if has_cloud_indicator and not prefer_local:
            if has_private_data and not allow_cloud_privacy:
                return RoutingDecision(
                    selected_tier=ModelTier.LOCAL_QWEN,
                    model_name="qwen3.5:9b",
                    is_cloud=False,
                    confidence=0.90,
                    reason="Complex architecture requested, but private data detected without cloud authorization. Enforced local Qwen 3.5 9B.",
                    task_classification="Privacy-Guarded Complex Planning",
                    requires_external_research=needs_research,
                    privacy_blocked_cloud=True
                )
            return RoutingDecision(
                selected_tier=ModelTier.ANTIGRAVITY_CLOUD,
                model_name="gemini-3.8-flash",
                is_cloud=True,
                confidence=0.85,
                reason="Task requires large-scale multi-repo cross-domain orchestration exceeding local VRAM context.",
                task_classification="Complex System Architecture",
                requires_external_research=needs_research,
                estimated_cost_usd=0.001
            )

        # 3. Check for Batman personal workstation partner dynamic
        if any(re.search(pat, lower) for pat in self.BATMAN_INDICATORS):
            return RoutingDecision(
                selected_tier=ModelTier.LOCAL_QWEN_BATMAN,
                model_name="qwen-batman:latest",
                is_cloud=False,
                confidence=0.98,
                reason="Task matches personal workstation thinking partner, memory context, and Batman dynamic.",
                task_classification="Personal Workstation Copilot",
                requires_external_research=needs_research
            )

        # 4. Check for pure deep text reasoning, theoretical analysis, or technical explanation -> qwen-text
        if any(re.search(pat, lower) for pat in self.TEXT_ANALYSIS_INDICATORS):
            return RoutingDecision(
                selected_tier=ModelTier.LOCAL_QWEN_TEXT,
                model_name="qwen-text:latest",
                is_cloud=False,
                confidence=0.96,
                reason="Task matches deep technical analysis and text reasoning suited for qwen-text:latest.",
                task_classification="Deep Technical Reasoning",
                requires_external_research=needs_research
            )

        # 5. Default: Local Qwen 3.5 9B base for autonomous tool execution, coding, memory, and research
        return RoutingDecision(
            selected_tier=ModelTier.LOCAL_QWEN,
            model_name="qwen3.5:9b",
            is_cloud=False,
            confidence=0.95,
            reason="Task is well-suited for high-efficiency local Qwen 3.5 9B reasoning with zero privacy leakage.",
            task_classification="Local Engineering & Autonomous Execution",
            requires_external_research=needs_research
        )

model_router = ModelRouter()
