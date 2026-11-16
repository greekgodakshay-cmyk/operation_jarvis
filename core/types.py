"""
Domain types, schemas, and enums for Operation Jarvis Agent Runtime.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    PLAN_FAILED = "plan_failed"
    CANCELLED = "cancelled"

class PermissionLevel(int, Enum):
    LEVEL_1_SAFE = 1        # Read-only inspection, search, analysis, non-destructive file reading
    LEVEL_2_CONTROLLED = 2  # Creating files, editing project files, installing dependencies, approved scripts
    LEVEL_3_RESTRICTED = 3  # Deleting files, modifying system configs, credentials, external calls, destructive ops

class RiskClass(str, Enum):
    READ_ONLY = "read_only"                      # Non-destructive inspection, queries, reading, telemetry
    REVERSIBLE = "reversible"                    # Internal workspace writes with rollback capability
    HIGH_RISK = "high_risk"                      # Deletion, process termination, system modifications
    EXTERNAL_SIDE_EFFECT = "external_side_effect"# Outbound email, calendar modification, publishing, external writes

class PlanGenerationError(Exception):
    """Raised when plan generation fails or output schema cannot be validated."""
    pass


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    RESEARCHER = "researcher"
    CODER = "coder"
    SYSTEM_OPS = "system_ops"
    BROWSER = "browser"
    REVIEWER = "reviewer"
    MEMORY = "memory"
    WORKSPACE = "workspace"
    TESTER = "tester"
    DOCUMENTER = "documenter"
    GIT = "git"

class TaskBudget(str, Enum):
    PLANNING = "planning"           # Fast structured JSON decomposition (768 tokens)
    SHORT_ANSWER = "short_answer"   # Conversational, voice, greetings (512 tokens)
    CODING = "coding"               # Multi-file code generation and diffs (2048 tokens)
    RESEARCH = "research"           # Multi-source synthesis and citations (3072 tokens)
    LONG_FORM = "long_form"         # In-depth architectural reports, scripts (4096 tokens)

TASK_TOKEN_BUDGETS: Dict[TaskBudget, int] = {
    TaskBudget.PLANNING: 768,
    TaskBudget.SHORT_ANSWER: 512,
    TaskBudget.CODING: 2048,
    TaskBudget.RESEARCH: 3072,
    TaskBudget.LONG_FORM: 4096,
}

class ToolCall(BaseModel):
    call_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    permission_level: PermissionLevel = PermissionLevel.LEVEL_1_SAFE

class ToolResult(BaseModel):
    call_id: str
    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    artifacts: List[str] = Field(default_factory=list)

class VerificationResult(BaseModel):
    is_verified: bool
    evidence: str
    checks_performed: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)

class ExecutionStep(BaseModel):
    step_number: int
    description: str
    tool_name: Optional[str] = None
    tool_arguments: Dict[str, Any] = Field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    assigned_agent: Optional[AgentRole] = None
    is_parallel_eligible: bool = False
    dependencies: List[int] = Field(default_factory=list)
    result: Optional[ToolResult] = None
    verification: Optional[VerificationResult] = None
    retry_count: int = 0
    error_message: Optional[str] = None

class SubObjective(BaseModel):
    id: str
    title: str
    assigned_agent: AgentRole = AgentRole.ORCHESTRATOR
    dependencies: List[str] = Field(default_factory=list)
    steps: List[ExecutionStep] = Field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result_summary: Optional[str] = None

class TaskPlan(BaseModel):
    objective: str
    reasoning: str
    steps: List[ExecutionStep] = Field(default_factory=list)
    sub_objectives: List[SubObjective] = Field(default_factory=list)
    parallel_groups: List[List[int]] = Field(default_factory=list)
    relevant_memories: List[Dict[str, Any]] = Field(default_factory=list)

class SharedTaskContext(BaseModel):
    task_id: str
    objective: str
    shared_state: Dict[str, Any] = Field(default_factory=dict)
    agent_outputs: Dict[str, Any] = Field(default_factory=dict)
    retrieved_memories: List[Dict[str, Any]] = Field(default_factory=list)
    discovered_skills: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    execution_log: List[Dict[str, Any]] = Field(default_factory=list)

class ApprovalRequest(BaseModel):
    request_id: str
    task_id: str
    step_number: int
    tool_name: str
    arguments: Dict[str, Any]
    reason: str
    permission_level: PermissionLevel = PermissionLevel.LEVEL_3_RESTRICTED
    created_at: str
    is_granted: Optional[bool] = None

class TaskRecord(BaseModel):
    task_id: str
    objective: str
    status: TaskStatus = TaskStatus.PENDING
    plan: Optional[TaskPlan] = None
    current_step_index: int = 0
    completed_steps: List[ExecutionStep] = Field(default_factory=list)
    pending_steps: List[ExecutionStep] = Field(default_factory=list)
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tool_results: List[ToolResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    pending_approval: Optional[ApprovalRequest] = None
    verification: Optional[VerificationResult] = None
    final_outcome: Optional[str] = None
    planned_steps_count: int = 0
    executed_steps_count: int = 0
    failed_steps_count: int = 0
    skipped_steps_count: int = 0
    verified_steps_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

class TraceEvent(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    task_id: str
    event_type: str  # "objective_received", "memory_retrieved", "plan_generated", "tool_call", "tool_result", "verification", "error", "approval_requested"
    details: Dict[str, Any] = Field(default_factory=dict)
