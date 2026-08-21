"""
Workflow Coordinator for Brite Casework Agent.
Orchestrates the 3-step morning sequence, enforces safeguarding gates,
records full execution traces, supports resume, and handles queue failures independently.
"""
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from .compat import Session

from .models import (
    ReferralModel,
    ResidentSnapshotModel,
    PolicyEvaluationModel,
    TriageNoteModel,
    ApprovalRequestModel,
    AuditLogModel,
    ProcessingState,
    PolicyDecision,
    WorkflowDisposition,
    ReferralDetailSchema,
    ReferralListSchema,
    QueueSummarySchema,
)
from .history_client import HistoryServiceClient
from .policy_engine import PolicyEngine, SafeguardingGate
from .gemini_service import GeminiTriageService
from .database import SessionLocal

logger = logging.getLogger("brite.coordinator")
HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE_DATA_PATH = os.path.join(HERE, "..", "data", "referral-queue.json")


class WorkflowCoordinator:
    def __init__(self, history_client: Optional[HistoryServiceClient] = None):
        self.history_client = history_client or HistoryServiceClient()
        self.gemini_service = GeminiTriageService()

    def seed_referrals_if_empty(self, db: Session) -> int:
        """Seed referrals table from referral-queue.json if empty."""
        count = db.query(ReferralModel).count()
        if count > 0:
            return count

        if not os.path.exists(QUEUE_DATA_PATH):
            logger.error(f"Referral queue data file not found at {QUEUE_DATA_PATH}")
            return 0

        with open(QUEUE_DATA_PATH, "r", encoding="utf-8") as f:
            queue = json.load(f)

        for item in queue:
            received_dt = datetime.fromisoformat(item["received_at"])
            ref = ReferralModel(
                referral_id=item["referral_id"],
                received_at=received_dt,
                resident_ref=item["resident_ref"],
                source=item["source"],
                summary=item["summary"],
                requested_action=item["requested_action"],
                urgency=item["urgency"],
                processing_state=ProcessingState.RECEIVED.value,
                policy_decision=None,
                workflow_disposition=WorkflowDisposition.PENDING.value,
            )
            db.add(ref)
            db.flush()

            # Record initial audit entry
            self._log_audit(
                db,
                ref.referral_id,
                step_name="QUEUE_INGESTION",
                event_type="REFERRAL_RECEIVED",
                details={
                    "received_at": item["received_at"],
                    "resident_ref": item["resident_ref"],
                    "source": item["source"],
                    "requested_action": item["requested_action"],
                    "urgency": item["urgency"],
                },
            )

        db.commit()
        return len(queue)

    async def process_referral(self, referral_id: str, db: Session) -> ReferralModel:
        """
        Processes an individual referral following the strict mandated order:
          1. Read Referral
          2. Pull Resident History & Household
          3. Under-18 Safeguard Gate (ACA-2026/2 §3.9)
          4. Policy Evaluation (ACA-2026/1)
          5. Gemini Triage Drafting (ONLY IF PERMITTED AND NO MINORS)
        """
        ref: ReferralModel = (
            db.query(ReferralModel)
            .filter(ReferralModel.referral_id == referral_id)
            .first()
        )
        if not ref:
            raise ValueError(f"Referral {referral_id} not found")

        try:
            # ----------------------------------------------------
            # STEP 1: PULL RESIDENT HISTORY
            # ----------------------------------------------------
            ref.processing_state = ProcessingState.FETCHING_HISTORY.value
            db.commit()

            self._log_audit(
                db,
                ref.referral_id,
                step_name="RESIDENT_HISTORY_PULL",
                event_type="API_REQUEST_INITIATED",
                details={"resident_ref": ref.resident_ref},
            )

            resident_data = await self.history_client.get_resident(ref.resident_ref)
            if not resident_data:
                # Controlled source failure handling
                ref.processing_state = ProcessingState.FAILED.value
                ref.workflow_disposition = WorkflowDisposition.FAILED.value
                self._log_audit(
                    db,
                    ref.referral_id,
                    step_name="RESIDENT_HISTORY_PULL",
                    event_type="RESIDENT_NOT_FOUND",
                    details={"error": f"Resident {ref.resident_ref} not found in history service"},
                )
                db.commit()
                return ref

            # Persist Resident Snapshot
            snapshot = ref.resident_snapshot
            if not snapshot:
                snapshot = ResidentSnapshotModel(
                    referral_id=ref.referral_id,
                    resident_ref=resident_data.get("resident_ref", ref.resident_ref),
                    status=resident_data.get("status", "Unknown"),
                    benefit_code=resident_data.get("benefit_code", "N/A"),
                    district=resident_data.get("district", "N/A"),
                    award_monthly=resident_data.get("award_monthly", 0.0),
                    household_raw=resident_data.get("household", []),
                    events_raw=resident_data.get("events", []),
                )
                db.add(snapshot)
            else:
                snapshot.status = resident_data.get("status", "Unknown")
                snapshot.benefit_code = resident_data.get("benefit_code", "N/A")
                snapshot.district = resident_data.get("district", "N/A")
                snapshot.award_monthly = resident_data.get("award_monthly", 0.0)
                snapshot.household_raw = resident_data.get("household", [])
                snapshot.events_raw = resident_data.get("events", [])

            ref.processing_state = ProcessingState.HISTORY_RETRIEVED.value
            db.commit()

            self._log_audit(
                db,
                ref.referral_id,
                step_name="RESIDENT_HISTORY_PULL",
                event_type="HISTORY_RECORD_STORED",
                details={
                    "benefit_code": snapshot.benefit_code,
                    "district": snapshot.district,
                    "award_monthly": snapshot.award_monthly,
                    "household_count": len(snapshot.household_raw or []),
                    "event_count": len(snapshot.events_raw or []),
                },
            )

            # ----------------------------------------------------
            # STEP 2: UNDER-18 SAFEGUARDING GATE & POLICY EVALUATION
            # ----------------------------------------------------
            ref.processing_state = ProcessingState.CHECKING_HOUSEHOLD.value
            db.commit()

            household_list = snapshot.household_raw
            policy_eval, enriched_members = PolicyEngine.evaluate(
                requested_action=ref.requested_action,
                summary=ref.summary,
                household_data=household_list,
            )

            # Check if any minor is present
            has_minor = any(m.is_minor for m in enriched_members)
            ref.has_under_18 = has_minor
            ref.policy_decision = policy_eval.decision.value

            # Update snapshot.household_raw with enriched data (age + minor flags)
            snapshot.household_raw = [
                {
                    "name": m.name,
                    "date_of_birth": m.date_of_birth,
                    "relationship": m.relationship,
                    "calculated_age": m.calculated_age,
                    "is_minor": m.is_minor,
                }
                for m in enriched_members
            ]

            # Persist Policy Evaluation
            eval_model = ref.policy_evaluation
            if not eval_model:
                eval_model = PolicyEvaluationModel(
                    referral_id=ref.referral_id,
                    decision=policy_eval.decision.value,
                    applicable_section=policy_eval.applicable_section,
                    rule_title=policy_eval.rule_title,
                    rationale=policy_eval.rationale,
                    triage_permitted=policy_eval.triage_permitted,
                    human_action_required=policy_eval.human_action_required,
                )
                db.add(eval_model)
            else:
                eval_model.decision = policy_eval.decision.value
                eval_model.applicable_section = policy_eval.applicable_section
                eval_model.rule_title = policy_eval.rule_title
                eval_model.rationale = policy_eval.rationale
                eval_model.triage_permitted = policy_eval.triage_permitted
                eval_model.human_action_required = policy_eval.human_action_required

            dec_val = getattr(policy_eval.decision, "value", str(policy_eval.decision))

            # ----------------------------------------------------
            # BRANCH A: UNDER-18 DETECTED -> HANDOFF (NO LLM CALL)
            # ----------------------------------------------------
            if dec_val == PolicyDecision.HANDOFF_REQUIRED.value:
                ref.processing_state = ProcessingState.HANDED_OFF.value
                ref.workflow_disposition = WorkflowDisposition.HANDOFF.value

                # Create suppression record for triage note
                triage_model = ref.triage_note
                suppression_text = (
                    f"TRIAGE GENERATION SUPPRESSED BY SAFEGUARDING GATE:\n"
                    f"Under Policy Amendment ACA-2026/2 §3.9, automated triage drafting is prohibited "
                    f"for households containing a person under 18. Case handed off to caseworker."
                )
                if not triage_model:
                    triage_model = TriageNoteModel(
                        referral_id=ref.referral_id,
                        summary_of_situation="Automated triage not permitted.",
                        recommended_next_steps="Caseworker to review referral and conduct manual triage.",
                        full_text=suppression_text,
                        drafted_by_llm=False,
                        llm_model=None,
                        suppression_reason=policy_eval.rationale,
                    )
                    db.add(triage_model)

                self._log_audit(
                    db,
                    ref.referral_id,
                    step_name="UNDER_18_SAFEGUARD_GATE",
                    event_type="HANDOFF_REQUIRED",
                    details={
                        "rule": policy_eval.applicable_section,
                        "reason": policy_eval.rationale,
                        "minors_identified": [
                            m.name for m in enriched_members if m.is_minor
                        ],
                        "llm_called": False,
                        "disposition": "HANDOFF",
                    },
                )
                db.commit()
                return ref

            # ----------------------------------------------------
            # BRANCH B: UNRESOLVABLE HOUSEHOLD -> SECTION 6.1 FAIL-SAFE
            # ----------------------------------------------------
            if dec_val == PolicyDecision.UNCLEAR.value:
                ref.processing_state = ProcessingState.AWAITING_APPROVAL.value
                ref.workflow_disposition = WorkflowDisposition.WAIT_FOR_APPROVAL.value

                # Create approval request for supervisor
                app_req = ref.approval_request
                if not app_req:
                    app_req = ApprovalRequestModel(
                        referral_id=ref.referral_id,
                        requested_action=ref.requested_action,
                        applicable_section=policy_eval.applicable_section,
                        context_summary=f"Section 6.1 Escalation: {policy_eval.rationale}\n\n--- Context ---\nResident Ref: {ref.resident_ref}\nHousehold Size: {len(household_list or [])}\nOriginal Summary: {ref.summary}",
                        status="PENDING",
                    )
                    db.add(app_req)

                self._log_audit(
                    db,
                    ref.referral_id,
                    step_name="POLICY_EVALUATION",
                    event_type="UNCERTAINTY_PROCEDURE_INVOKED",
                    details={
                        "procedure": "ACA-2026/1 §6.1",
                        "rule": policy_eval.applicable_section,
                        "reason": policy_eval.rationale,
                        "llm_called": False,
                        "disposition": "WAIT_FOR_APPROVAL",
                    },
                )
                db.commit()
                return ref

            # ----------------------------------------------------
            # BRANCH C: PROHIBITED ACTION -> ESCALATE UNDER SECTION 4
            # ----------------------------------------------------
            dec_val = getattr(policy_eval.decision, "value", str(policy_eval.decision))

            if dec_val == PolicyDecision.PROHIBITED.value:
                ref.processing_state = ProcessingState.ESCALATED.value
                ref.workflow_disposition = WorkflowDisposition.ESCALATE.value

                app_req = ref.approval_request
                if not app_req:
                    app_req = ApprovalRequestModel(
                        referral_id=ref.referral_id,
                        requested_action=ref.requested_action,
                        applicable_section=policy_eval.applicable_section,
                        context_summary=f"Section 4 Escalation: {policy_eval.rationale}\n\n--- Context ---\nResident Ref: {ref.resident_ref}\nHousehold Size: {len(household_list or [])}\nAward Monthly: £{snapshot.award_monthly}\nOriginal Summary: {ref.summary}",
                        status="PENDING",
                    )
                    db.add(app_req)

                self._log_audit(
                    db,
                    ref.referral_id,
                    step_name="POLICY_EVALUATION",
                    event_type="ESCALATION_REQUIRED",
                    details={
                        "rule": policy_eval.applicable_section,
                        "reason": policy_eval.rationale,
                        "prohibited_action": ref.requested_action,
                        "llm_called": False,
                        "disposition": "ESCALATE",
                    },
                )
                db.commit()
                return ref

            # ----------------------------------------------------
            # BRANCH D: APPROVAL REQUIRED (e.g. Appeals Reinstatement Note)
            # ----------------------------------------------------
            if dec_val == PolicyDecision.APPROVAL_REQUIRED.value:
                # If triage drafting for supervisor is permitted under Section 2.4:
                if policy_eval.triage_permitted:
                    ref.processing_state = ProcessingState.DRAFTING_TRIAGE.value
                    db.commit()

                    triage_schema = await self.gemini_service.draft_triage(
                        referral={
                            "resident_ref": ref.resident_ref,
                            "source": ref.source,
                            "summary": ref.summary,
                            "requested_action": ref.requested_action,
                            "urgency": ref.urgency,
                        },
                        resident=resident_data,
                        household=household_list,
                        events=snapshot.events_raw or [],
                        policy_section=policy_eval.applicable_section,
                        has_minor=False,
                        triage_permitted=True,
                    )

                    triage_model = ref.triage_note
                    if not triage_model:
                        triage_model = TriageNoteModel(
                            referral_id=ref.referral_id,
                            summary_of_situation=triage_schema.summary_of_situation,
                            recommended_next_steps=triage_schema.recommended_next_steps,
                            full_text=triage_schema.full_text,
                            drafted_by_llm=triage_schema.drafted_by_llm,
                            llm_model=triage_schema.llm_model,
                            suppression_reason=None,
                        )
                        db.add(triage_model)

                app_req = ref.approval_request
                if not app_req:
                    app_req = ApprovalRequestModel(
                        referral_id=ref.referral_id,
                        requested_action=ref.requested_action,
                        applicable_section=policy_eval.applicable_section,
                        context_summary=policy_eval.rationale,
                        status="PENDING",
                    )
                    db.add(app_req)

                ref.processing_state = ProcessingState.AWAITING_APPROVAL.value
                ref.workflow_disposition = WorkflowDisposition.WAIT_FOR_APPROVAL.value

                self._log_audit(
                    db,
                    ref.referral_id,
                    step_name="APPROVAL_GATE",
                    event_type="APPROVAL_REQUEST_CREATED",
                    details={
                        "rule": policy_eval.applicable_section,
                        "action": ref.requested_action,
                        "reason": policy_eval.rationale,
                        "disposition": "WAIT_FOR_APPROVAL",
                    },
                )
                db.commit()
                return ref

            # ----------------------------------------------------
            # BRANCH E: ALLOWED -> DRAFT TRIAGE NOTE WITH AGENT
            # ----------------------------------------------------
            if dec_val == PolicyDecision.ALLOWED.value:
                ref.processing_state = ProcessingState.DRAFTING_TRIAGE.value
                db.commit()

                self._log_audit(
                    db,
                    ref.referral_id,
                    step_name="TRIAGE_GENERATION",
                    event_type="AGENT_INVOCATION_AUTHORIZED",
                    details={
                        "rule": policy_eval.applicable_section,
                        "has_minor": False,
                        "actor": "CaseworkAgent",
                    },
                )

                triage_schema = await self.gemini_service.draft_triage(
                    referral={
                        "resident_ref": ref.resident_ref,
                        "source": ref.source,
                        "summary": ref.summary,
                        "requested_action": ref.requested_action,
                        "urgency": ref.urgency,
                    },
                    resident=resident_data,
                    household=household_list,
                    events=snapshot.events_raw or [],
                    policy_section=policy_eval.applicable_section,
                    has_minor=False,
                    triage_permitted=True,
                )

                triage_model = ref.triage_note
                if not triage_model:
                    triage_model = TriageNoteModel(
                        referral_id=ref.referral_id,
                        summary_of_situation=triage_schema.summary_of_situation,
                        recommended_next_steps=triage_schema.recommended_next_steps,
                        full_text=triage_schema.full_text,
                        drafted_by_llm=triage_schema.drafted_by_llm,
                        llm_model=triage_schema.llm_model,
                        suppression_reason=None,
                    )
                    db.add(triage_model)
                else:
                    triage_model.summary_of_situation = triage_schema.summary_of_situation
                    triage_model.recommended_next_steps = triage_schema.recommended_next_steps
                    triage_model.full_text = triage_schema.full_text
                    triage_model.drafted_by_llm = triage_schema.drafted_by_llm
                    triage_model.llm_model = triage_schema.llm_model

                ref.processing_state = ProcessingState.COMPLETED.value
                ref.workflow_disposition = WorkflowDisposition.COMPLETED.value

                self._log_audit(
                    db,
                    ref.referral_id,
                    step_name="TRIAGE_GENERATION",
                    event_type="TRIAGE_NOTE_DRAFTED",
                    details={
                        "drafted_by_llm": triage_schema.drafted_by_llm,
                        "model": triage_schema.llm_model,
                        "summary_len": len(triage_schema.summary_of_situation),
                    },
                )
                db.commit()
                return ref

        except Exception as e:
            logger.error(f"Error processing referral {referral_id}: {e}", exc_info=True)
            ref.processing_state = ProcessingState.PAUSED.value
            ref.workflow_disposition = WorkflowDisposition.FAILED.value
            ref.error_message = str(e)
            self._log_audit(
                db,
                ref.referral_id,
                step_name="WORKFLOW_ERROR",
                event_type="EXCEPTION_CAUGHT",
                details={"error": str(e)},
            )
            db.commit()
            return ref

    async def process_all_queue(self, db: Session) -> List[ReferralModel]:
        """
        Process the entire queue independently.
        One referral reaching HANDOFF, ESCALATE, or FAILED does NOT terminate the rest.
        """
        referrals = db.query(ReferralModel).order_by(ReferralModel.received_at.asc()).all()
        results = []
        for ref in referrals:
            res = await self.process_referral(ref.referral_id, db)
            results.append(res)
        return results

    async def resume_referral(self, referral_id: str, db: Session) -> ReferralModel:
        """
        Resumes processing a referral from where it left off,
        ensuring current policies (including Amendment ACA-2026/2) are applied unconditionally.
        """
        ref = db.query(ReferralModel).filter(ReferralModel.referral_id == referral_id).first()
        if not ref:
            raise ValueError(f"Referral {referral_id} not found")

        ref.is_resumed = True
        self._log_audit(
            db,
            ref.referral_id,
            step_name="RESUME_OPERATION",
            event_type="WORKFLOW_RESUMED",
            details={"previous_state": ref.processing_state, "previous_disposition": ref.workflow_disposition},
        )
        db.commit()

        return await self.process_referral(referral_id, db)

    def _log_audit(
        self,
        db: Session,
        referral_id: str,
        step_name: str,
        event_type: str,
        details: Dict[str, Any],
        actor: str = "BriteCaseworkAgent",
    ):
        log = AuditLogModel(
            referral_id=referral_id,
            step_name=step_name,
            event_type=event_type,
            actor=actor,
            details=details,
            timestamp=datetime.utcnow(),
        )
        db.add(log)
