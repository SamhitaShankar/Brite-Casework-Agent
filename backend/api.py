"""
FastAPI REST API for Brite Casework Agent.
Exposes endpoints for queue inspection, workflow execution, supervisor approvals, and audit trails.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import get_db, init_db, SessionLocal
from .models import (
    ReferralModel,
    ApprovalRequestModel,
    AuditLogModel,
    ResidentSnapshotModel,
    PolicyEvaluationModel,
    TriageNoteModel,
    ReferralListSchema,
    ReferralDetailSchema,
    QueueSummarySchema,
    AuditLogSchema,
    ProcessingState,
    WorkflowDisposition,
)
from .coordinator import WorkflowCoordinator

app = FastAPI(
    title="Brite Casework Agent API",
    description="Deterministic policy-governed casework assistant with under-18 safeguarding gate and supervisor approval boundaries.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

coordinator = WorkflowCoordinator()


@app.on_event("startup")
def on_startup():
    init_db()
    with SessionLocal() as db:
        coordinator.seed_referrals_if_empty(db)


class DecisionRequest(BaseModel):
    decision_notes: Optional[str] = "Approved by supervisor"
    supervisor_id: Optional[str] = "SUP-01"


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "brite-casework-agent"}


@app.get("/api/queue/summary", response_model=QueueSummarySchema)
def get_queue_summary(db: Session = Depends(get_db)):
    total = db.query(ReferralModel).count()
    completed = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.COMPLETED.value).count()
    handed_off = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.HANDOFF.value).count()
    escalated = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.ESCALATE.value).count()
    awaiting = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.WAIT_FOR_APPROVAL.value).count()
    pending = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.PENDING.value).count()
    failed = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.FAILED.value).count()

    return QueueSummarySchema(
        total_referrals=total,
        completed=completed,
        handed_off=handed_off,
        escalated=escalated,
        awaiting_approval=awaiting,
        pending=pending,
        failed=failed,
    )


@app.get("/api/referrals", response_model=List[ReferralListSchema])
def list_referrals(
    disposition: Optional[str] = Query(None, description="Filter by workflow disposition"),
    db: Session = Depends(get_db),
):
    query = db.query(ReferralModel).order_by(ReferralModel.received_at.asc())
    if disposition:
        query = query.filter(ReferralModel.workflow_disposition == disposition.upper())

    results = []
    for ref in query.all():
        section = ref.policy_evaluation.applicable_section if ref.policy_evaluation else None
        has_triage = ref.triage_note is not None and ref.triage_note.suppression_reason is None
        results.append(
            ReferralListSchema(
                referral_id=ref.referral_id,
                received_at=ref.received_at,
                resident_ref=ref.resident_ref,
                source=ref.source,
                summary=ref.summary,
                requested_action=ref.requested_action,
                urgency=ref.urgency,
                processing_state=ref.processing_state,
                policy_decision=ref.policy_decision,
                workflow_disposition=ref.workflow_disposition,
                has_under_18=ref.has_under_18,
                applicable_section=section,
                triage_drafted=has_triage,
                updated_at=ref.updated_at,
            )
        )
    return results


@app.get("/api/referrals/{referral_id}", response_model=ReferralDetailSchema)
def get_referral_detail(referral_id: str, db: Session = Depends(get_db)):
    ref = db.query(ReferralModel).filter(ReferralModel.referral_id == referral_id).first()
    if not ref:
        raise HTTPException(status_code=404, detail=f"Referral {referral_id} not found")

    snapshot_schema = None
    if ref.resident_snapshot:
        s = ref.resident_snapshot
        enriched_household = []
        for m in (s.household_raw or []):
            dob_str = m.get("date_of_birth", "")
            age = m.get("calculated_age")
            if age is None and dob_str:
                from backend.policy_engine import calculate_age
                age = calculate_age(dob_str)
            is_minor = m.get("is_minor")
            if is_minor is None:
                is_minor = (age is not None and age < 18)
            enriched_household.append({
                "name": m.get("name", "Unknown"),
                "date_of_birth": dob_str,
                "relationship": m.get("relationship", "Unknown"),
                "calculated_age": age,
                "is_minor": bool(is_minor),
            })

        snapshot_schema = {
            "resident_ref": s.resident_ref,
            "status": s.status,
            "benefit_code": s.benefit_code,
            "district": s.district,
            "award_monthly": s.award_monthly,
            "household": enriched_household,
            "events": s.events_raw or [],
            "retrieved_at": s.retrieved_at,
        }

    eval_schema = None
    if ref.policy_evaluation:
        e = ref.policy_evaluation
        eval_schema = {
            "decision": e.decision,
            "applicable_section": e.applicable_section,
            "rule_title": e.rule_title,
            "rationale": e.rationale,
            "triage_permitted": e.triage_permitted,
            "human_action_required": e.human_action_required,
            "evaluated_at": e.evaluated_at,
        }

    triage_schema = None
    if ref.triage_note:
        t = ref.triage_note
        triage_schema = {
            "summary_of_situation": t.summary_of_situation,
            "recommended_next_steps": t.recommended_next_steps,
            "full_text": t.full_text,
            "drafted_by_llm": t.drafted_by_llm,
            "llm_model": t.llm_model,
            "suppression_reason": t.suppression_reason,
            "generated_at": t.generated_at,
        }

    app_req_schema = None
    if ref.approval_request:
        a = ref.approval_request
        app_req_schema = {
            "id": a.id,
            "referral_id": a.referral_id,
            "requested_action": a.requested_action,
            "applicable_section": a.applicable_section,
            "context_summary": a.context_summary,
            "status": a.status,
            "decided_at": a.decided_at,
            "decision_notes": a.decision_notes,
            "supervisor_id": a.supervisor_id,
        }

    logs = [
        AuditLogSchema(
            id=log.id,
            referral_id=log.referral_id,
            timestamp=log.timestamp,
            step_name=log.step_name,
            event_type=log.event_type,
            actor=log.actor,
            details=log.details or {},
        )
        for log in ref.audit_logs
    ]

    return ReferralDetailSchema(
        referral_id=ref.referral_id,
        received_at=ref.received_at,
        resident_ref=ref.resident_ref,
        source=ref.source,
        summary=ref.summary,
        requested_action=ref.requested_action,
        urgency=ref.urgency,
        processing_state=ref.processing_state,
        policy_decision=ref.policy_decision,
        workflow_disposition=ref.workflow_disposition,
        has_under_18=ref.has_under_18,
        is_resumed=ref.is_resumed,
        resident_snapshot=snapshot_schema,
        policy_evaluation=eval_schema,
        triage_note=triage_schema,
        approval_request=app_req_schema,
        audit_logs=logs,
        updated_at=ref.updated_at,
    )


@app.post("/api/referrals/{referral_id}/process")
async def process_single_referral(referral_id: str, db: Session = Depends(get_db)):
    ref = await coordinator.process_referral(referral_id, db)
    return {"message": "Processed successfully", "referral_id": ref.referral_id, "disposition": ref.workflow_disposition}


@app.post("/api/referrals/process-all")
async def process_all(db: Session = Depends(get_db)):
    results = await coordinator.process_all_queue(db)
    return {
        "message": "Queue processed",
        "processed_count": len(results),
        "results": [
            {"referral_id": r.referral_id, "disposition": r.workflow_disposition, "decision": r.policy_decision}
            for r in results
        ],
    }


@app.post("/api/referrals/{referral_id}/resume")
async def resume_referral(referral_id: str, db: Session = Depends(get_db)):
    ref = await coordinator.resume_referral(referral_id, db)
    return {"message": "Resumed successfully", "referral_id": ref.referral_id, "disposition": ref.workflow_disposition}


@app.post("/api/referrals/{referral_id}/approve")
def approve_request(referral_id: str, payload: DecisionRequest, db: Session = Depends(get_db)):
    ref = db.query(ReferralModel).filter(ReferralModel.referral_id == referral_id).first()
    if not ref or not ref.approval_request:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if ref.approval_request.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve: Approval request is in '{ref.approval_request.status}' state, expected 'PENDING'.",
        )

    if ref.processing_state != ProcessingState.AWAITING_APPROVAL.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve: Referral is in state '{ref.processing_state}', expected 'AWAITING_APPROVAL'.",
        )

    if ref.has_under_18 or ref.policy_decision == "HANDOFF_REQUIRED":
        raise HTTPException(
            status_code=403,
            detail="Safety Invariant Violation: Minor(s) present in household. Case must remain in Children & Family Services handoff under Amendment ACA-2026/2 §3.9.",
        )

    valid_supervisor_id = (payload.supervisor_id or "SUP-01").strip()
    valid_notes = (payload.decision_notes or "Approved by supervisor").strip()

    req = ref.approval_request
    req.status = "APPROVED"
    req.decided_at = datetime.utcnow()
    req.decision_notes = valid_notes
    req.supervisor_id = valid_supervisor_id

    ref.workflow_disposition = WorkflowDisposition.COMPLETED.value
    ref.processing_state = ProcessingState.COMPLETED.value

    coordinator._log_audit(
        db,
        referral_id=ref.referral_id,
        step_name="SUPERVISOR_ACTION",
        event_type="REQUEST_APPROVED",
        details={
            "supervisor_id": valid_supervisor_id,
            "decision_notes": valid_notes,
            "action": req.requested_action,
            "section": req.applicable_section,
        },
        actor=valid_supervisor_id,
    )
    db.commit()
    return {"message": "Approval recorded", "referral_id": referral_id, "status": "APPROVED"}


@app.post("/api/referrals/{referral_id}/reject")
def reject_request(referral_id: str, payload: DecisionRequest, db: Session = Depends(get_db)):
    ref = db.query(ReferralModel).filter(ReferralModel.referral_id == referral_id).first()
    if not ref or not ref.approval_request:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if ref.approval_request.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject: Approval request is in '{ref.approval_request.status}' state, expected 'PENDING'.",
        )

    if ref.processing_state != ProcessingState.AWAITING_APPROVAL.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject: Referral is in state '{ref.processing_state}', expected 'AWAITING_APPROVAL'.",
        )

    valid_supervisor_id = (payload.supervisor_id or "SUP-01").strip()
    valid_notes = (payload.decision_notes or "Rejected by supervisor; escalated for formal departmental determination.").strip()

    req = ref.approval_request
    req.status = "REJECTED"
    req.decided_at = datetime.utcnow()
    req.decision_notes = valid_notes
    req.supervisor_id = valid_supervisor_id

    ref.workflow_disposition = WorkflowDisposition.ESCALATE.value
    ref.processing_state = ProcessingState.ESCALATED.value

    coordinator._log_audit(
        db,
        referral_id=ref.referral_id,
        step_name="SUPERVISOR_ACTION",
        event_type="REQUEST_REJECTED",
        details={
            "supervisor_id": valid_supervisor_id,
            "decision_notes": valid_notes,
            "action": req.requested_action,
            "section": req.applicable_section,
        },
        actor=valid_supervisor_id,
    )
    db.commit()
    return {"message": "Rejection recorded", "referral_id": referral_id, "status": "REJECTED"}


@app.get("/api/audit-logs", response_model=List[AuditLogSchema])
def get_all_audit_logs(limit: int = 100, db: Session = Depends(get_db)):
    logs = db.query(AuditLogModel).order_by(AuditLogModel.timestamp.desc()).limit(limit).all()
    return logs



@app.get("/api/policy/rules")
def get_policy_rules():
    return {
        "policy_reference": "ACA-2026/1 + ACA-2026/2",
        "in_force": "Immediately",
        "jurisdiction": "Calder County Department of Household Services",
        "sections": [
            {
                "section": "ACA-2026/2 §3.9",
                "title": "Safeguarding Gate: Households with Minors Under 18",
                "type": "HANDOFF_REQUIRED",
                "description": "Drafting triage notes for households including anyone under 18 requires caseworker judgement from the outset. Automated triage drafting is prohibited. Case context is preserved and handed off.",
            },
            {
                "section": "ACA-2026/1 §2.4",
                "title": "Draft Triage Note for Review",
                "type": "ALLOWED",
                "description": "Permitted without approval. Generates an advisory triage proposal. Has no legal effect until adopted by a human caseworker.",
            },
            {
                "section": "ACA-2026/1 §3.2",
                "title": "Award Suspension, Termination, or Reinstatement",
                "type": "PROHIBITED / APPROVAL_REQUIRED",
                "description": "Assistant must not perform or draft preparatory actions. Escalates to supervisor under Section 4.",
            },
            {
                "section": "ACA-2026/1 §3.4",
                "title": "Payment Details Changes",
                "type": "PROHIBITED",
                "description": "Assistant must not alter bank or card payment details without supervisor sign-off.",
            },
            {
                "section": "ACA-2026/1 §6.1",
                "title": "Uncertainty Fail-Safe",
                "type": "UNCLEAR",
                "description": "Where authority is unclear or household cannot be established, treated as requiring supervisor review.",
            },
        ],
    }
