"""
SQLAlchemy & Pydantic models for Brite Casework Agent.
Strict separation of:
  - ProcessingState (what step the agent is at)
  - PolicyDecision (what the authority policy evaluated)
  - WorkflowDisposition (the human/workflow outcome)
"""
from enum import Enum
from datetime import datetime
from typing import List, Optional, Any, Dict
from .compat import (
    Column,
    String,
    Float,
    DateTime,
    Boolean,
    Text,
    Integer,
    ForeignKey,
    JSON,
    relationship,
    BaseModel,
    Field,
)
from .database import Base


# ==========================================
# ENUMS
# ==========================================

class ProcessingState(str, Enum):
    RECEIVED = "RECEIVED"
    FETCHING_HISTORY = "FETCHING_HISTORY"
    HISTORY_RETRIEVED = "HISTORY_RETRIEVED"
    CHECKING_HOUSEHOLD = "CHECKING_HOUSEHOLD"
    HOUSEHOLD_CHECKED = "HOUSEHOLD_CHECKED"
    EVALUATING_POLICY = "EVALUATING_POLICY"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    DRAFTING_TRIAGE = "DRAFTING_TRIAGE"
    TRIAGE_DRAFTED = "TRIAGE_DRAFTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    HANDED_OFF = "HANDED_OFF"
    ESCALATED = "ESCALATED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


class PolicyDecision(str, Enum):
    ALLOWED = "ALLOWED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    PROHIBITED = "PROHIBITED"
    HANDOFF_REQUIRED = "HANDOFF_REQUIRED"
    UNCLEAR = "UNCLEAR"


class WorkflowDisposition(str, Enum):
    PENDING = "PENDING"
    CONTINUE = "CONTINUE"
    WAIT_FOR_APPROVAL = "WAIT_FOR_APPROVAL"
    HANDOFF = "HANDOFF"
    ESCALATE = "ESCALATE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ==========================================
# SQLALCHEMY DATABASE MODELS
# ==========================================

class ReferralModel(Base):
    __tablename__ = "referrals"

    referral_id = Column(String(50), primary_key=True, index=True)
    received_at = Column(DateTime, nullable=False)
    resident_ref = Column(String(50), nullable=False, index=True)
    source = Column(String(100), nullable=False)
    summary = Column(Text, nullable=False)
    requested_action = Column(String(150), nullable=False)
    urgency = Column(String(50), nullable=False, default="Standard")

    # Workflow State Separation
    processing_state = Column(
        String(50), nullable=False, default=ProcessingState.RECEIVED.value
    )
    policy_decision = Column(String(50), nullable=True)
    workflow_disposition = Column(
        String(50), nullable=False, default=WorkflowDisposition.PENDING.value
    )

    # Flags & Timestamps
    has_under_18 = Column(Boolean, nullable=True)
    is_resumed = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    resident_snapshot = relationship(
        "ResidentSnapshotModel", back_populates="referral", uselist=False, cascade="all, delete-orphan"
    )
    policy_evaluation = relationship(
        "PolicyEvaluationModel", back_populates="referral", uselist=False, cascade="all, delete-orphan"
    )
    triage_note = relationship(
        "TriageNoteModel", back_populates="referral", uselist=False, cascade="all, delete-orphan"
    )
    approval_request = relationship(
        "ApprovalRequestModel", back_populates="referral", uselist=False, cascade="all, delete-orphan"
    )
    audit_logs = relationship(
        "AuditLogModel", back_populates="referral", cascade="all, delete-orphan", order_by="AuditLogModel.timestamp"
    )


class ResidentSnapshotModel(Base):
    __tablename__ = "resident_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referral_id = Column(String(50), ForeignKey("referrals.referral_id"), unique=True)
    resident_ref = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    benefit_code = Column(String(50), nullable=False)
    district = Column(String(100), nullable=False)
    award_monthly = Column(Float, nullable=False)
    household_raw = Column(JSON, nullable=True)
    events_raw = Column(JSON, nullable=True)
    retrieved_at = Column(DateTime, default=datetime.utcnow)

    referral = relationship("ReferralModel", back_populates="resident_snapshot")


class PolicyEvaluationModel(Base):
    __tablename__ = "policy_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referral_id = Column(String(50), ForeignKey("referrals.referral_id"), unique=True)
    decision = Column(String(50), nullable=False)
    applicable_section = Column(String(100), nullable=False)
    rule_title = Column(String(200), nullable=False)
    rationale = Column(Text, nullable=False)
    triage_permitted = Column(Boolean, nullable=False, default=False)
    human_action_required = Column(String(250), nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow)

    referral = relationship("ReferralModel", back_populates="policy_evaluation")


class TriageNoteModel(Base):
    __tablename__ = "triage_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referral_id = Column(String(50), ForeignKey("referrals.referral_id"), unique=True)
    summary_of_situation = Column(Text, nullable=False)
    recommended_next_steps = Column(Text, nullable=False)
    full_text = Column(Text, nullable=False)
    drafted_by_llm = Column(Boolean, nullable=False, default=False)
    llm_model = Column(String(100), nullable=True)
    suppression_reason = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)

    referral = relationship("ReferralModel", back_populates="triage_note")


class ApprovalRequestModel(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referral_id = Column(String(50), ForeignKey("referrals.referral_id"), unique=True)
    requested_action = Column(String(150), nullable=False)
    applicable_section = Column(String(100), nullable=False)
    context_summary = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, APPROVED, REJECTED
    decided_at = Column(DateTime, nullable=True)
    decision_notes = Column(Text, nullable=True)
    supervisor_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    referral = relationship("ReferralModel", back_populates="approval_request")


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referral_id = Column(String(50), ForeignKey("referrals.referral_id"), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    step_name = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    actor = Column(String(100), default="BriteCaseworkAgent")
    details = Column(JSON, nullable=False)

    referral = relationship("ReferralModel", back_populates="audit_logs")


# ==========================================
# PYDANTIC SCHEMAS (API Transfer Models)
# ==========================================

class HouseholdMemberSchema(BaseModel):
    name: str
    date_of_birth: str
    relationship: str
    calculated_age: Optional[int] = None
    is_minor: Optional[bool] = None


class CaseEventSchema(BaseModel):
    date: str
    type: str
    detail: str


class ResidentSnapshotSchema(BaseModel):
    resident_ref: str
    status: str
    benefit_code: str
    district: str
    award_monthly: float
    household: List[HouseholdMemberSchema] = []
    events: List[CaseEventSchema] = []
    retrieved_at: Optional[datetime] = None


class PolicyEvaluationSchema(BaseModel):
    decision: PolicyDecision
    applicable_section: str
    rule_title: str
    rationale: str
    triage_permitted: bool
    human_action_required: Optional[str] = None
    evaluated_at: Optional[datetime] = None


class TriageNoteSchema(BaseModel):
    summary_of_situation: str
    recommended_next_steps: str
    full_text: str
    drafted_by_llm: bool
    llm_model: Optional[str] = None
    suppression_reason: Optional[str] = None
    generated_at: Optional[datetime] = None


class ApprovalRequestSchema(BaseModel):
    id: Optional[int] = None
    referral_id: str
    requested_action: str
    applicable_section: str
    context_summary: str
    status: str
    decided_at: Optional[datetime] = None
    decision_notes: Optional[str] = None
    supervisor_id: Optional[str] = None


class AuditLogSchema(BaseModel):
    id: Optional[int] = None
    referral_id: str
    timestamp: datetime
    step_name: str
    event_type: str
    actor: str
    details: Dict[str, Any]


class ReferralDetailSchema(BaseModel):
    referral_id: str
    received_at: datetime
    resident_ref: str
    source: str
    summary: str
    requested_action: str
    urgency: str
    processing_state: ProcessingState
    policy_decision: Optional[PolicyDecision] = None
    workflow_disposition: WorkflowDisposition
    has_under_18: Optional[bool] = None
    is_resumed: bool = False
    error_message: Optional[str] = None
    resident_snapshot: Optional[ResidentSnapshotSchema] = None
    policy_evaluation: Optional[PolicyEvaluationSchema] = None
    triage_note: Optional[TriageNoteSchema] = None
    approval_request: Optional[ApprovalRequestSchema] = None
    audit_logs: List[AuditLogSchema] = []
    updated_at: Optional[datetime] = None


class ReferralListSchema(BaseModel):
    referral_id: str
    received_at: datetime
    resident_ref: str
    source: str
    summary: str
    requested_action: str
    urgency: str
    processing_state: ProcessingState
    policy_decision: Optional[PolicyDecision] = None
    workflow_disposition: WorkflowDisposition
    has_under_18: Optional[bool] = None
    error_message: Optional[str] = None
    applicable_section: Optional[str] = None
    triage_drafted: bool = False
    updated_at: Optional[datetime] = None


class QueueSummarySchema(BaseModel):
    total_referrals: int
    completed: int
    handed_off: int
    escalated: int
    awaiting_approval: int
    pending: int
    failed: int
