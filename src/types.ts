export type ProcessingState =
  | 'RECEIVED'
  | 'FETCHING_HISTORY'
  | 'HISTORY_RETRIEVED'
  | 'CHECKING_HOUSEHOLD'
  | 'HOUSEHOLD_CHECKED'
  | 'EVALUATING_POLICY'
  | 'POLICY_EVALUATED'
  | 'DRAFTING_TRIAGE'
  | 'TRIAGE_DRAFTED'
  | 'AWAITING_APPROVAL'
  | 'HANDED_OFF'
  | 'ESCALATED'
  | 'COMPLETED'
  | 'FAILED'
  | 'PAUSED';

export type PolicyDecision =
  | 'ALLOWED'
  | 'APPROVAL_REQUIRED'
  | 'PROHIBITED'
  | 'HANDOFF_REQUIRED'
  | 'UNCLEAR';

export type WorkflowDisposition =
  | 'PENDING'
  | 'CONTINUE'
  | 'WAIT_FOR_APPROVAL'
  | 'HANDOFF'
  | 'ESCALATE'
  | 'COMPLETED'
  | 'FAILED';

export interface HouseholdMember {
  name: string;
  date_of_birth: string;
  relationship: string;
  calculated_age?: number;
  is_minor?: boolean;
}

export interface CaseEvent {
  date: string;
  type: string;
  detail: string;
}

export interface ResidentSnapshot {
  resident_ref: string;
  status: string;
  benefit_code: string;
  district: string;
  award_monthly: number;
  household: HouseholdMember[];
  events: CaseEvent[];
  retrieved_at?: string;
}

export interface PolicyEvaluation {
  decision: PolicyDecision;
  applicable_section: string;
  rule_title: string;
  rationale: string;
  triage_permitted: boolean;
  human_action_required?: string;
  evaluated_at?: string;
}

export interface TriageNote {
  summary_of_situation: string;
  recommended_next_steps: string;
  full_text: string;
  drafted_by_llm: boolean;
  llm_model?: string;
  suppression_reason?: string;
  generated_at?: string;
}

export interface ApprovalRequest {
  id?: number;
  referral_id: string;
  requested_action: string;
  applicable_section: string;
  context_summary: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  decided_at?: string;
  decision_notes?: string;
  supervisor_id?: string;
}

export interface AuditLog {
  id?: number;
  referral_id: string;
  timestamp: string;
  step_name: string;
  event_type: string;
  actor: string;
  details: Record<string, any>;
}

export interface ReferralDetail {
  referral_id: string;
  received_at: string;
  resident_ref: string;
  source: string;
  summary: string;
  requested_action: string;
  urgency: string;
  processing_state: ProcessingState;
  policy_decision?: PolicyDecision;
  workflow_disposition: WorkflowDisposition;
  has_under_18?: boolean;
  is_resumed?: boolean;
  resident_snapshot?: ResidentSnapshot;
  policy_evaluation?: PolicyEvaluation;
  triage_note?: TriageNote;
  approval_request?: ApprovalRequest;
  audit_logs: AuditLog[];
  updated_at?: string;
}

export interface ReferralListItem {
  referral_id: string;
  received_at: string;
  resident_ref: string;
  source: string;
  summary: string;
  requested_action: string;
  urgency: string;
  processing_state: ProcessingState;
  policy_decision?: PolicyDecision;
  workflow_disposition: WorkflowDisposition;
  has_under_18?: boolean;
  applicable_section?: string;
  triage_drafted: boolean;
  updated_at?: string;
}

export interface QueueSummary {
  total_referrals: number;
  completed: number;
  handed_off: number;
  escalated: number;
  awaiting_approval: number;
  pending: number;
  failed: number;
}
