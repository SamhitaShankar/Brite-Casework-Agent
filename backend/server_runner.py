"""
Standalone standard-library HTTP Server for Brite Casework Backend.
Runs on 127.0.0.1:8001 and delegates to SQLAlchemy/Database, Coordinator, Policy Engine, and Models.
"""
import sys
import json
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

from backend.database import get_db, init_db, SessionLocal
from backend.models import (
    ReferralModel,
    ApprovalRequestModel,
    AuditLogModel,
    ResidentSnapshotModel,
    PolicyEvaluationModel,
    TriageNoteModel,
    ProcessingState,
    WorkflowDisposition,
)
from backend.coordinator import WorkflowCoordinator

PORT = 8001
coordinator = WorkflowCoordinator()

# Initialize DB & seed initial referrals
init_db()
with SessionLocal() as db:
    coordinator.seed_referrals_if_empty(db)


def serialize_referral_list_item(ref: ReferralModel) -> dict:
    section = ref.policy_evaluation.applicable_section if ref.policy_evaluation else None
    has_triage = ref.triage_note is not None and ref.triage_note.suppression_reason is None
    return {
        "referral_id": ref.referral_id,
        "received_at": ref.received_at.isoformat() if hasattr(ref.received_at, "isoformat") else str(ref.received_at),
        "resident_ref": ref.resident_ref,
        "source": ref.source,
        "summary": ref.summary,
        "requested_action": ref.requested_action,
        "urgency": ref.urgency,
        "processing_state": ref.processing_state,
        "policy_decision": ref.policy_decision,
        "workflow_disposition": ref.workflow_disposition,
        "has_under_18": ref.has_under_18,
        "applicable_section": section,
        "triage_drafted": has_triage,
        "updated_at": ref.updated_at.isoformat() if hasattr(ref.updated_at, "isoformat") else str(ref.updated_at),
    }


def serialize_referral_detail(ref: ReferralModel) -> dict:
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
            "retrieved_at": s.retrieved_at.isoformat() if hasattr(s.retrieved_at, "isoformat") else str(s.retrieved_at),
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
            "evaluated_at": e.evaluated_at.isoformat() if hasattr(e.evaluated_at, "isoformat") else str(e.evaluated_at),
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
            "generated_at": t.generated_at.isoformat() if hasattr(t.generated_at, "isoformat") else str(t.generated_at),
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
            "decided_at": a.decided_at.isoformat() if a.decided_at and hasattr(a.decided_at, "isoformat") else (str(a.decided_at) if a.decided_at else None),
            "decision_notes": a.decision_notes,
            "supervisor_id": a.supervisor_id,
        }

    logs = [
        {
            "id": log.id,
            "referral_id": log.referral_id,
            "timestamp": log.timestamp.isoformat() if hasattr(log.timestamp, "isoformat") else str(log.timestamp),
            "step_name": log.step_name,
            "event_type": log.event_type,
            "actor": log.actor,
            "details": log.details or {},
        }
        for log in ref.audit_logs
    ]

    return {
        "referral_id": ref.referral_id,
        "received_at": ref.received_at.isoformat() if hasattr(ref.received_at, "isoformat") else str(ref.received_at),
        "resident_ref": ref.resident_ref,
        "source": ref.source,
        "summary": ref.summary,
        "requested_action": ref.requested_action,
        "urgency": ref.urgency,
        "processing_state": ref.processing_state,
        "policy_decision": ref.policy_decision,
        "workflow_disposition": ref.workflow_disposition,
        "has_under_18": ref.has_under_18,
        "is_resumed": ref.is_resumed,
        "resident_snapshot": snapshot_schema,
        "policy_evaluation": eval_schema,
        "triage_note": triage_schema,
        "approval_request": app_req_schema,
        "audit_logs": logs,
        "updated_at": ref.updated_at.isoformat() if hasattr(ref.updated_at, "isoformat") else str(ref.updated_at),
    }


class CaseworkAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: any):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        body = json.dumps(data).encode("utf-8")
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            if not path.startswith("/api"):
                path = "/api" + path
            query = parse_qs(parsed.query)

            with SessionLocal() as db:
                if path in ("/api/health", "/health"):
                    return self._send_json(200, {"status": "ok", "service": "brite-casework-agent"})

                elif path == "/api/queue/summary":
                    total = db.query(ReferralModel).count()
                    completed = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.COMPLETED.value).count()
                    handed_off = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.HANDOFF.value).count()
                    escalated = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.ESCALATE.value).count()
                    awaiting = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.WAIT_FOR_APPROVAL.value).count()
                    pending = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.PENDING.value).count()
                    failed = db.query(ReferralModel).filter(ReferralModel.workflow_disposition == WorkflowDisposition.FAILED.value).count()

                    return self._send_json(200, {
                        "total_referrals": total,
                        "completed": completed,
                        "handed_off": handed_off,
                        "escalated": escalated,
                        "awaiting_approval": awaiting,
                        "pending": pending,
                        "failed": failed,
                    })

                elif path == "/api/referrals":
                    disp = query.get("disposition", [None])[0]
                    q = db.query(ReferralModel).order_by(ReferralModel.received_at.asc())
                    if disp:
                        q = q.filter(ReferralModel.workflow_disposition == disp.upper())
                    results = [serialize_referral_list_item(r) for r in q.all()]
                    return self._send_json(200, results)

                elif path.startswith("/api/referrals/"):
                    parts = path.split("/")
                    if len(parts) == 4:
                        referral_id = parts[3]
                        ref = db.query(ReferralModel).filter(ReferralModel.referral_id == referral_id).first()
                        if not ref:
                            return self._send_json(404, {"error": f"Referral {referral_id} not found"})
                        return self._send_json(200, serialize_referral_detail(ref))

                elif path == "/api/audit-logs":
                    logs = db.query(AuditLogModel).order_by(AuditLogModel.timestamp.desc()).limit(100).all()
                    res = [
                        {
                            "id": log.id,
                            "referral_id": log.referral_id,
                            "timestamp": log.timestamp.isoformat() if hasattr(log.timestamp, "isoformat") else str(log.timestamp),
                            "step_name": log.step_name,
                            "event_type": log.event_type,
                            "actor": log.actor,
                            "details": log.details or {},
                        }
                        for log in logs
                    ]
                    return self._send_json(200, res)

                elif path == "/api/policy/rules":
                    return self._send_json(200, {
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
                        ],
                    })

            self._send_json(404, {"error": "Not found", "path": path})
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json(500, {"error": str(e), "type": type(e).__name__})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not path.startswith("/api"):
            path = "/api" + path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}

        try:
            with SessionLocal() as db:
                if path == "/api/reset-demo":
                    from backend.compat import _GLOBAL_STORE
                    if isinstance(_GLOBAL_STORE, list):
                        _GLOBAL_STORE.clear()
                    count = coordinator.seed_referrals_if_empty(db)
                    return self._send_json(200, {"message": "Database reset to initial overnight state", "referrals_seeded": count})

                elif path == "/api/referrals/process-all":
                    results = asyncio.run(coordinator.process_all_queue(db))
                    return self._send_json(200, {
                        "message": "Queue processed",
                        "processed_count": len(results),
                        "results": [
                            {"referral_id": r.referral_id, "disposition": r.workflow_disposition, "decision": r.policy_decision}
                            for r in results
                        ],
                    })

                elif path.startswith("/api/referrals/"):
                    parts = path.split("/")
                    # Pattern: /api/referrals/{id}/{action}
                    if len(parts) == 5:
                        referral_id = parts[3]
                        action = parts[4]

                        if action == "process":
                            ref = asyncio.run(coordinator.process_referral(referral_id, db))
                            return self._send_json(200, {
                                "message": "Processed successfully",
                                "referral_id": ref.referral_id,
                                "disposition": ref.workflow_disposition,
                            })

                        elif action == "resume":
                            ref = asyncio.run(coordinator.resume_referral(referral_id, db))
                            return self._send_json(200, {
                                "message": "Resumed successfully",
                                "referral_id": ref.referral_id,
                                "disposition": ref.workflow_disposition,
                            })

                        elif action == "approve":
                            ref = db.query(ReferralModel).filter(ReferralModel.referral_id == referral_id).first()
                            if not ref or not ref.approval_request:
                                return self._send_json(404, {"error": "Approval request not found"})

                            if ref.approval_request.status != "PENDING":
                                return self._send_json(400, {"error": f"Cannot approve: status is '{ref.approval_request.status}'"})

                            if ref.processing_state != ProcessingState.AWAITING_APPROVAL.value:
                                return self._send_json(400, {"error": f"Cannot approve: state is '{ref.processing_state}'"})

                            if ref.has_under_18 or ref.policy_decision == "HANDOFF_REQUIRED":
                                return self._send_json(403, {"error": "Safety Invariant Violation: Minor in household. Must remain in handoff."})

                            valid_sup = (payload.get("supervisor_id") or "SUP-01").strip()
                            valid_notes = (payload.get("decision_notes") or "Approved by supervisor").strip()

                            req = ref.approval_request
                            req.status = "APPROVED"
                            req.decided_at = datetime.utcnow()
                            req.decision_notes = valid_notes
                            req.supervisor_id = valid_sup

                            ref.workflow_disposition = WorkflowDisposition.COMPLETED.value
                            ref.processing_state = ProcessingState.COMPLETED.value

                            coordinator._log_audit(
                                db,
                                referral_id=ref.referral_id,
                                step_name="SUPERVISOR_ACTION",
                                event_type="REQUEST_APPROVED",
                                details={
                                    "supervisor_id": valid_sup,
                                    "decision_notes": valid_notes,
                                    "action": req.requested_action,
                                    "section": req.applicable_section,
                                },
                                actor=valid_sup,
                            )
                            db.commit()
                            return self._send_json(200, {"message": "Approval recorded", "referral_id": referral_id, "status": "APPROVED"})

                        elif action == "reject":
                            ref = db.query(ReferralModel).filter(ReferralModel.referral_id == referral_id).first()
                            if not ref or not ref.approval_request:
                                return self._send_json(404, {"error": "Approval request not found"})

                            if ref.approval_request.status != "PENDING":
                                return self._send_json(400, {"error": f"Cannot reject: status is '{ref.approval_request.status}'"})

                            if ref.processing_state != ProcessingState.AWAITING_APPROVAL.value:
                                return self._send_json(400, {"error": f"Cannot reject: state is '{ref.processing_state}'"})

                            valid_sup = (payload.get("supervisor_id") or "SUP-01").strip()
                            valid_notes = (payload.get("decision_notes") or "Rejected by supervisor").strip()

                            req = ref.approval_request
                            req.status = "REJECTED"
                            req.decided_at = datetime.utcnow()
                            req.decision_notes = valid_notes
                            req.supervisor_id = valid_sup

                            ref.workflow_disposition = WorkflowDisposition.ESCALATE.value
                            ref.processing_state = ProcessingState.ESCALATED.value

                            coordinator._log_audit(
                                db,
                                referral_id=ref.referral_id,
                                step_name="SUPERVISOR_ACTION",
                                event_type="REQUEST_REJECTED",
                                details={
                                    "supervisor_id": valid_sup,
                                    "decision_notes": valid_notes,
                                    "action": req.requested_action,
                                    "section": req.applicable_section,
                                },
                                actor=valid_sup,
                            )
                            db.commit()
                            return self._send_json(200, {"message": "Rejection recorded", "referral_id": referral_id, "status": "REJECTED"})

            self._send_json(404, {"error": "Not found", "path": path})
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                self._send_json(500, {"error": str(e), "type": type(e).__name__})
            except Exception:
                pass


def run_server():
    server_address = ("127.0.0.1", PORT)
    httpd = HTTPServer(server_address, CaseworkAPIHandler)
    print(f"[Python Casework Backend] Serving HTTP on 127.0.0.1:{PORT}...", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server()
