"""
Master Autonomous Agent Orchestrator for Operation Jarvis.
Executes the full lifecycle: Receive -> Understand -> Retrieve -> Plan -> Tool Loop ->
Observe -> Self-Correct -> Verify -> Store -> Report.
"""
import time
from typing import Any, Dict, List, Optional
from config.settings import settings
from core.types import (
    TaskRecord, TaskStatus, TaskPlan, ExecutionStep,
    StepStatus, ToolCall, ToolResult, VerificationResult, ApprovalRequest,
    SharedTaskContext, AgentRole, PlanGenerationError
)
from core.dynamic_planner import dynamic_planner
from core.hierarchical_planner import hierarchical_planner
from core.agent_orchestra import agent_orchestra
from core.verification import verification_engine
from core.self_correction import self_correction_engine
from core.llm_client import llm_client
from registry.capability_registry import capability_registry
from registry.memory_adapter import memory_adapter
from storage.task_db import task_db
from storage.audit_logger import audit_logger
from security.policy_engine import ApprovalRequiredError

class JarvisOrchestrator:
    def __init__(self):
        self.db = task_db
        self.logger = audit_logger
        self.planner = dynamic_planner
        self.verifier = verification_engine
        self.corrector = self_correction_engine

    def execute_objective(
        self,
        objective: str,
        task_id: Optional[str] = None,
        approval_token: Optional[str] = None
    ) -> TaskRecord:
        """Entry point for executing a new objective."""
        record = self.db.create_task(objective=objective, task_id=task_id)
        self.logger.log_event(
            task_id=record.task_id,
            event_type="objective_received",
            details={"objective": objective}
        )
        return self._run_execution_loop(record.task_id, approval_token=approval_token)

    def resume_task(self, task_id: str, approval_token: Optional[str] = None) -> TaskRecord:
        """Resumes an interrupted or approval-paused task."""
        record = self.db.get_task(task_id)
        if not record:
            raise ValueError(f"Task '{task_id}' not found.")

        self.logger.log_event(
            task_id=task_id,
            event_type="task_resumed",
            details={"previous_status": record.status.value, "approval_token": approval_token}
        )
        return self._run_execution_loop(task_id, resume=True, approval_token=approval_token)

    def cancel_task(self, task_id: str, reason: str = "User cancelled.") -> TaskRecord:
        self.db.update_task_status(task_id, TaskStatus.CANCELLED, error=reason)
        self.logger.log_event(
            task_id=task_id,
            event_type="task_cancelled",
            details={"reason": reason}
        )
        return self.db.get_task(task_id)

    def emergency_stop(self, reason: str = "Emergency stop triggered by operator.") -> Dict[str, Any]:
        """Halts all execution across policy engine, task state machine, and active child processes."""
        from security.policy_engine import policy_engine
        policy_res = policy_engine.trigger_emergency_stop()
        
        # Terminate any running child subprocesses
        terminated_pids = []
        try:
            import psutil
            current_proc = psutil.Process()
            for child in current_proc.children(recursive=True):
                try:
                    terminated_pids.append(child.pid)
                    child.terminate()
                except Exception:
                    pass
        except Exception:
            pass

        active_tasks = self.db.list_tasks(status=TaskStatus.RUNNING)
        for t in active_tasks:
            self.cancel_task(t.task_id, reason=reason)
            
        return {
            "ok": True,
            "policy": policy_res,
            "aborted_tasks": [t.task_id for t in active_tasks],
            "terminated_subprocesses": terminated_pids,
            "message": "Emergency stop activated. All running tasks aborted, child processes terminated, and execution gates locked."
        }

    def reset_emergency_stop(self) -> Dict[str, Any]:
        """Resets emergency stop and returns orchestrator to operational status."""
        from security.policy_engine import policy_engine
        return policy_engine.reset_emergency_stop()

    def _run_execution_loop(
        self,
        task_id: str,
        resume: bool = False,
        approval_token: Optional[str] = None
    ) -> TaskRecord:
        task = self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' does not exist.")

        start_time = time.time()

        # Step 1: Planning (generate plan if task has no plan yet)
        if not task.plan:
            self.db.update_task_status(task_id, TaskStatus.PLANNING)
            self.logger.log_event(task_id, "planning_started", {"objective": task.objective})
            
            try:
                try:
                    plan = hierarchical_planner.create_hierarchical_plan(task.objective)
                except Exception:
                    plan = self.planner.create_plan(task.objective)
            except PlanGenerationError as pge:
                err_msg = f"Planning failed: {str(pge)}"
                self.db.update_task_status(task_id, TaskStatus.PLAN_FAILED, error=err_msg)
                self.logger.log_event(task_id, "planning_failed", {"error": err_msg})
                return self.db.get_task(task_id)
            except Exception as ex:
                err_msg = f"Planning failed with unexpected error: {str(ex)}"
                self.db.update_task_status(task_id, TaskStatus.PLAN_FAILED, error=err_msg)
                self.logger.log_event(task_id, "planning_failed", {"error": err_msg})
                return self.db.get_task(task_id)

            self.db.save_plan(task_id, plan)
            self.logger.log_event(task_id, "plan_generated", {
                "reasoning": plan.reasoning,
                "step_count": len(plan.steps)
            })
            task = self.db.get_task(task_id)

        # Initialize shared blackboard context across agents
        shared_context = SharedTaskContext(
            task_id=task_id,
            objective=task.objective,
            shared_state={},
            retrieved_memories=task.plan.relevant_memories if task.plan else []
        )

        # Step 2: Step-by-Step Execution Loop
        self.db.update_task_status(task_id, TaskStatus.RUNNING)
        pending_steps = list(task.pending_steps)

        for step in pending_steps:
            # Check timeout
            if (time.time() - start_time) > settings.task_timeout_seconds:
                err_msg = f"Task timed out after {settings.task_timeout_seconds} seconds."
                self.db.update_task_status(task_id, TaskStatus.FAILED, error=err_msg)
                return self.db.get_task(task_id)

            # Check if task was cancelled externally
            current_state = self.db.get_task(task_id)
            if current_state.status == TaskStatus.CANCELLED:
                return current_state

            # Execute Step with Bounded Retries & Self-Correction
            step_success = False
            last_result: Optional[ToolResult] = None

            while not step_success and step.retry_count <= settings.max_retries_per_step:
                if not step.tool_name:
                    # Non-tool reasoning / synthesis step
                    desc_lower = step.description.lower()
                    # Enforce strict prerequisite: Only execute email summarization when actual email data was retrieved
                    if any(w in desc_lower for w in ["summarize", "summary", "synthesize", "extract"]) and any(w in desc_lower for w in ["email", "emails", "gmail", "inbox"]):
                        prior_emails = []
                        current_completed = self.db.get_task(task_id).completed_steps
                        for cs in current_completed:
                            if cs.result and isinstance(cs.result.output, dict):
                                prior_emails.extend(cs.result.output.get("emails", []))

                        if not prior_emails:
                            step.status = StepStatus.SKIPPED
                            step.error_message = "Summarization halted: No email data was retrieved from prior steps."
                            self.db.record_step_progress(task_id, step)
                            self.db.block_task(
                                task_id=task_id,
                                reason="Task BLOCKED: Cannot execute summarization because zero email data was retrieved."
                            )
                            self.logger.log_event(task_id, "step_skipped_missing_data", {
                                "step": step.step_number,
                                "description": step.description,
                                "reason": "No email data present to summarize."
                            })
                            return self.db.get_task(task_id)

                    step_success = True
                    last_result = ToolResult(
                        call_id=f"step-{step.step_number}-synth",
                        tool_name="reasoning",
                        success=True,
                        output=f"Reasoned: {step.description}"
                    )
                    break

                # Validate planned tool call against live registered schema before execution
                if not capability_registry.get_tool(step.tool_name):
                    step.status = StepStatus.FAILED
                    step.error_message = f"Schema validation error: Tool '{step.tool_name}' is not registered in capability registry."
                    last_result = ToolResult(
                        call_id=f"step-{step.step_number}-invalid",
                        tool_name=step.tool_name,
                        success=False,
                        error=step.error_message
                    )
                    break

                try:
                    # Execute tool call via capability registry
                    result = capability_registry.execute_tool(
                        name=step.tool_name,
                        arguments=step.tool_arguments,
                        task_id=task_id,
                        step_number=step.step_number,
                        approval_token=approval_token
                    )
                    last_result = result

                    # Verify step output
                    verif = self.verifier.verify_step_result(step, result)
                    step.verification = verif

                    if verif.is_verified:
                        step_success = True
                        step.status = StepStatus.COMPLETED
                        step.result = result
                        break
                    else:
                        # Check if step returned INDETERMINATE
                        if verif.details.get("status") == "INDETERMINATE" or "INDETERMINATE" in verif.evidence:
                            step.status = StepStatus.FAILED
                            step.error_message = verif.evidence
                            self.db.record_step_progress(task_id, step, tool_result=result)
                            self.db.update_task_status(task_id, TaskStatus.FAILED, error=f"Task FAILED: {verif.evidence}")
                            self.logger.log_event(task_id, "task_failed_indeterminate", {
                                "reason": verif.evidence,
                                "step": step.step_number,
                                "tool": step.tool_name
                            })
                            return self.db.get_task(task_id)

                        # Check if step is blocked by authentication or missing credentials
                        if verif.details.get("status") == "AUTHENTICATION_REQUIRED" or "BLOCKED" in verif.evidence:
                            step.status = StepStatus.FAILED
                            step.error_message = verif.evidence
                            self.db.record_step_progress(task_id, step, tool_result=result)
                            self.db.block_task(
                                task_id=task_id,
                                reason=f"Task BLOCKED: {verif.evidence}",
                                details=verif.details
                            )
                            self.logger.log_event(task_id, "task_blocked", {
                                "reason": verif.evidence,
                                "step": step.step_number,
                                "tool": step.tool_name
                            })
                            return self.db.get_task(task_id)

                        # Attempt self-correction for general errors
                        if self.corrector.should_retry(step, result, settings.max_retries_per_step):
                            self.db.update_task_status(task_id, TaskStatus.RECOVERING)
                            self.logger.log_event(task_id, "recovery_attempt", {
                                "step": step.step_number,
                                "retry_count": step.retry_count,
                                "error": result.error
                            })
                            step = self.corrector.formulate_recovery_step(step, result)
                        else:
                            step.status = StepStatus.FAILED
                            step.error_message = f"Verification failed: {verif.evidence}"
                            break

                except ApprovalRequiredError as e:
                    # Level 3 gate: transition to WAITING_FOR_APPROVAL and safely halt
                    self.db.record_approval_request(e.approval_request)
                    self.logger.log_event(task_id, "approval_required", {
                        "request_id": e.approval_request.request_id,
                        "tool": e.approval_request.tool_name,
                        "reason": e.approval_request.reason
                    })
                    return self.db.get_task(task_id)

                except Exception as ex:
                    step.status = StepStatus.FAILED
                    step.error_message = str(ex)
                    break

            # Record step completion in durable DB
            self.db.record_step_progress(task_id, step, tool_result=last_result)

            if not step_success:
                err = f"Step {step.step_number} ('{step.description}') failed. {step.error_message}"
                completed_so_far = self.db.get_task(task_id).completed_steps
                if len(completed_so_far) > 0:
                    self.db.update_task_status(task_id, TaskStatus.PARTIALLY_COMPLETED, error=err)
                else:
                    self.db.update_task_status(task_id, TaskStatus.FAILED, error=err)
                return self.db.get_task(task_id)

        # Step 3: Final Verification & Evidence Aggregation
        final_task_record = self.db.get_task(task_id)
        final_verif = self.verifier.verify_final_objective(
            objective=final_task_record.objective,
            completed_steps=final_task_record.completed_steps,
            errors=final_task_record.errors
        )
        
        # Independent Reviewer Agent Audit
        rev_audit = agent_orchestra.review_final_task(final_task_record, shared_context)
        if not rev_audit.is_verified and final_verif.is_verified and final_task_record.errors:
            final_verif.is_verified = False
            final_verif.evidence += f" | {rev_audit.evidence}"

        if final_verif.is_verified and len(final_task_record.completed_steps) > 0 and bool(final_verif.evidence and final_verif.evidence.strip()):
            outcome_text = f"Objective verified and completed successfully in {len(final_task_record.completed_steps)} steps."
            self.db.complete_task(task_id, final_verif, outcome_text, status=TaskStatus.COMPLETED)
            self.logger.log_event(task_id, "task_completed", {
                "verified": True,
                "evidence": final_verif.evidence
            })
        else:
            status_hint = final_verif.details.get("status", TaskStatus.FAILED.value)
            if status_hint == TaskStatus.BLOCKED.value or "BLOCKED" in final_verif.evidence:
                final_status = TaskStatus.BLOCKED
            elif len(final_task_record.completed_steps) > 0:
                final_status = TaskStatus.PARTIALLY_COMPLETED
            else:
                final_status = TaskStatus.FAILED

            outcome_text = f"Objective verification not satisfied: {final_verif.evidence}"
            self.db.complete_task(task_id, final_verif, outcome_text, status=final_status)
            self.logger.log_event(task_id, f"task_{final_status.value}", {
                "verified": False,
                "evidence": final_verif.evidence,
                "final_status": final_status.value
            })

        return self.db.get_task(task_id)

orchestrator = JarvisOrchestrator()
