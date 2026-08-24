import React, { useState, useEffect } from 'react';
import { ReferralDetail, HouseholdMember, AuditLog } from '../types';
import {
  X,
  FileText,
  User,
  Users,
  ShieldCheck,
  Sparkles,
  Baby,
  History,
  Check,
  Ban,
  AlertTriangle,
  Lock,
  Clock,
  FileCheck,
  AlertOctagon,
  Calendar,
  ChevronDown,
  ChevronRight,
  Info,
  UserCheck,
  ShieldAlert,
  ArrowRightCircle,
  HelpCircle,
  Activity,
} from 'lucide-react';

const parseUTC = (ds: string | Date | undefined) => {
  if (!ds) return new Date();
  const s = String(ds);
  return new Date(s.endsWith('Z') ? s : s + 'Z');
};

interface CaseDetailModalProps {
  referral: ReferralDetail | null;
  onClose: () => void;
  onApprove: (referralId: string, notes: string) => void;
  onReject: (referralId: string, notes: string) => void;
  onResume: (referralId: string) => void;
}

// Helper to calculate member age accurately as of 2026-03-17 intake date
function getMemberAge(member: { date_of_birth?: string; calculated_age?: number }): number {
  if (typeof member.calculated_age === 'number') {
    return member.calculated_age;
  }
  if (!member.date_of_birth) return 0;
  try {
    const parts = member.date_of_birth.trim().split('-').map(Number);
    if (parts.length === 3) {
      const [birthYear, birthMonth, birthDay] = parts;
      const refYear = 2026, refMonth = 3, refDay = 17;
      let age = refYear - birthYear;
      if (refMonth < birthMonth || (refMonth === birthMonth && refDay < birthDay)) {
        age--;
      }
      return Math.max(0, age);
    }
  } catch (e) {
    // fallback
  }
  return 0;
}

function isMemberMinor(member: { date_of_birth?: string; calculated_age?: number; is_minor?: boolean }): boolean {
  if (typeof member.is_minor === 'boolean') {
    return member.is_minor;
  }
  return getMemberAge(member) < 18;
}

export const CaseDetailModal: React.FC<CaseDetailModalProps> = ({
  referral,
  onClose,
  onApprove,
  onReject,
  onResume,
}) => {
  const [activeTab, setActiveTab] = useState<'case_overview' | 'safeguards_policy' | 'agent_proposal' | 'timeline_audit'>('case_overview');
  const [decisionNotes, setDecisionNotes] = useState('');
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  useEffect(() => {
    if (referral) {
      setActiveTab('case_overview');
      setExpandedLogId(null);
      setShowTechnicalDetails(false);
    }
  }, [referral?.referral_id]);

  if (!referral) return null;

  const isMinorPresent = referral.has_under_18 === true;
  const isProhibited = referral.workflow_disposition === 'ESCALATE';
  const isAwaitingApproval = referral.workflow_disposition === 'WAIT_FOR_APPROVAL';
  const isCompleted = referral.workflow_disposition === 'COMPLETED';
  const isPaused = referral.workflow_disposition === 'FAILED';
  const isPending = referral.workflow_disposition === 'PENDING';

  // Human-friendly operational disposition
  const getOperationalDisposition = () => {
    switch (referral.workflow_disposition) {
      case 'COMPLETED':
        return {
          title: 'Ready for Caseworker Review',
          badge: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800',
          summary: 'Routine triage proposal generated. Ready for caseworker adoption.',
        };
      case 'HANDOFF':
        return {
          title: 'Human Safeguarding Handoff',
          badge: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950/60 dark:text-indigo-300 border-indigo-300 dark:border-indigo-800',
          summary: 'Household includes a resident under 18. Transferred to human caseworkers.',
        };
      case 'ESCALATE':
        return {
          title: 'Escalation Required (Prohibited)',
          badge: 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 border-rose-300 dark:border-rose-800',
          summary: 'Requested action is prohibited under Section 3. Escalated to supervisor.',
        };
      case 'WAIT_FOR_APPROVAL':
        return {
          title: 'Supervisor Approval Required',
          badge: 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300 dark:border-amber-800',
          summary: 'Requires supervisor sign-off before entitlement or payment action.',
        };
      case 'FAILED':
        return {
          title: 'Processing Paused',
          badge: 'bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border-red-300 dark:border-red-800',
          summary: 'Processing paused due to an error. Technical retry available.',
        };
      default:
        return {
          title: 'Awaiting Processing',
          badge: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border-slate-300 dark:border-slate-700',
          summary: 'Intake referral received in overnight queue.',
        };
    }
  };

  // Human-friendly audit event formatter
  const formatAuditEvent = (log: AuditLog) => {
    switch (log.event_type) {
      case 'REFERRAL_RECEIVED':
        return {
          title: 'Intake Referral Received',
          desc: `Referral logged from source: ${referral.source} for resident ${referral.resident_ref}.`,
          icon: FileText,
          color: 'text-blue-500',
        };
      case 'HISTORY_RETRIEVED':
        return {
          title: 'Resident Snapshot Retrieved',
          desc: `Fetched benefit record, district data, and household roster (${referral.resident_snapshot?.household?.length || 0} members).`,
          icon: Users,
          color: 'text-indigo-500',
        };
      case 'SAFEGUARDING_EVALUATED':
        if (log.details?.has_under_18 === true) {
          return {
            title: 'Under-18 Safeguarding Gate Triggered',
            desc: `Minor under 18 identified in household. Automated drafting blocked under ACA-2026/2 §3.9.`,
            icon: Baby,
            color: 'text-indigo-600',
          };
        }
        return {
          title: 'Under-18 Safeguarding Gate Passed',
          desc: 'Confirmed all household members are 18 or older. Passes safeguarding gate.',
          icon: ShieldCheck,
          color: 'text-emerald-500',
        };
      case 'POLICY_RULE_EVALUATED':
        return {
          title: `Statutory Policy Evaluated: ${log.details?.applicable_section || 'ACA-2026/1'}`,
          desc: `Policy determination: ${log.details?.decision || 'Evaluated'}. Rationale: ${log.details?.rationale || 'Rule matched'}.`,
          icon: Lock,
          color: log.details?.decision === 'PROHIBITED' ? 'text-rose-500' : 'text-blue-500',
        };
      case 'TRIAGE_NOTE_DRAFTED':
      case 'AGENT_INVOCATION_AUTHORIZED':
        return {
          title: 'Casework Agent Triage Proposal Drafted',
          desc: 'Generated structured situation summary and recommended next steps for caseworker review under §2.4.',
          icon: Sparkles,
          color: 'text-emerald-500',
        };
      case 'HANDOFF_TO_HUMAN':
        return {
          title: 'Case Transferred to Human Caseworker',
          desc: `Reason: ${log.details?.reason || 'Safeguarding handoff required'}.`,
          icon: UserCheck,
          color: 'text-indigo-600',
        };
      case 'APPROVAL_REQUESTED':
        return {
          title: 'Supervisor Approval Request Created',
          desc: `Supervisor sign-off queued for action: ${log.details?.requested_action || referral.requested_action}.`,
          icon: Clock,
          color: 'text-amber-500',
        };
      case 'SUPERVISOR_APPROVED':
        return {
          title: 'Supervisor Approved Request',
          desc: `Approved by ${log.actor || 'Supervisor'}. Notes: ${log.details?.decision_notes || 'Approved'}.`,
          icon: Check,
          color: 'text-emerald-600',
        };
      case 'SUPERVISOR_REJECTED':
        return {
          title: 'Supervisor Rejected Request',
          desc: `Declined by ${log.actor || 'Supervisor'}. Notes: ${log.details?.decision_notes || 'Rejected'}.`,
          icon: Ban,
          color: 'text-rose-600',
        };
      default:
        return {
          title: log.step_name.replace(/_/g, ' '),
          desc: log.event_type.replace(/_/g, ' '),
          icon: Info,
          color: 'text-slate-500',
        };
    }
  };

  const opStatus = getOperationalDisposition();

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/70 backdrop-blur-xs flex justify-center items-center p-3 sm:p-5">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-4xl w-full shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Modal Header */}
        <div className="shrink-0 px-6 py-4 bg-slate-50 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-blue-100 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400 rounded-xl border border-blue-200 dark:border-blue-800/50">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2 flex-wrap">
                <h2 className="text-base font-bold text-slate-900 dark:text-white font-mono">
                  {referral.referral_id}
                </h2>
                <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                  Resident: {referral.resident_ref}
                </span>
                <span className={`text-xs px-2.5 py-0.5 rounded-full font-bold border ${opStatus.badge}`}>
                  {opStatus.title}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Received: {parseUTC(referral.received_at).toLocaleString()} • Source: {referral.source} • Priority: {referral.urgency}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Operational 5-Point Summary Ribbon */}
        <div className="shrink-0 px-6 py-3 bg-slate-100/90 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div>
              <span className="text-slate-500 dark:text-slate-400 font-semibold">Under-18 Safeguarding:</span>{' '}
              {referral.has_under_18 === true ? (
                <strong className="text-indigo-600 dark:text-indigo-400">Triggered (Minor in Home)</strong>
              ) : referral.has_under_18 === false ? (
                <strong className="text-emerald-600 dark:text-emerald-400">Gate Passed (Adults Only)</strong>
              ) : (
                <span className="text-slate-500">Unchecked</span>
              )}
            </div>
            <div>
              <span className="text-slate-500 dark:text-slate-400 font-semibold">Statutory Authority:</span>{' '}
              <strong className="font-mono text-slate-800 dark:text-slate-200">
                {referral.policy_evaluation?.applicable_section || 'ACA-2026/1 §2.4'}
              </strong>
            </div>
            <div>
              <span className="text-slate-500 dark:text-slate-400 font-semibold">Next Action By:</span>{' '}
              <strong className="text-slate-800 dark:text-slate-200">
                {isMinorPresent
                  ? 'Caseworker (Family Services)'
                  : isAwaitingApproval
                  ? 'Supervisor (Sign-Off)'
                  : isProhibited
                  ? 'Supervisor (Escalation)'
                  : 'Caseworker (Review Draft)'}
              </strong>
            </div>
          </div>
        </div>

        {/* Tab Navigation - 4 Non-Overlapping Tabs */}
        <div className="shrink-0 px-6 bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex space-x-2 sm:space-x-6 overflow-x-auto">
          <button
            onClick={() => setActiveTab('case_overview')}
            className={`py-3 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
              activeTab === 'case_overview'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <User className="w-3.5 h-3.5" />
            <span>1. Case & Resident Overview</span>
          </button>

          <button
            onClick={() => setActiveTab('safeguards_policy')}
            className={`py-3 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
              activeTab === 'safeguards_policy'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>2. Safeguards & Policy Basis</span>
          </button>

          <button
            onClick={() => setActiveTab('agent_proposal')}
            className={`py-3 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
              activeTab === 'agent_proposal'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>3. Triage Proposal</span>
          </button>

          <button
            onClick={() => setActiveTab('timeline_audit')}
            className={`py-3 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
              activeTab === 'timeline_audit'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>4. Case Timeline & Audit ({referral.audit_logs.length})</span>
          </button>
        </div>

        {/* Tab Content Body */}
        <div className="p-6 overflow-y-auto flex-1 text-slate-800 dark:text-slate-200">
          {/* TAB 1: CASE & RESIDENT OVERVIEW */}
          {activeTab === 'case_overview' && (
            <div className="space-y-6">
              {/* Primary 5-Question Casework Answer Box */}
              <div className="p-4 rounded-xl bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800/60 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-blue-900 dark:text-blue-300 flex items-center gap-1.5">
                  <Info className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  <span>Casework Operational Assessment</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <div className="font-semibold text-slate-700 dark:text-slate-300">1. What happened?</div>
                    <p className="text-slate-600 dark:text-slate-400 mt-0.5">
                      {referral.summary}
                    </p>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-700 dark:text-slate-300">2. Why did this determination occur?</div>
                    <p className="text-slate-600 dark:text-slate-400 mt-0.5">
                      {referral.policy_evaluation?.rationale || (
                        isMinorPresent
                          ? 'A household member is under 18 years of age. Policy ACA-2026/2 §3.9 halts AI drafting and requires human safeguarding casework.'
                          : isProhibited
                          ? 'Requested action is prohibited under Section 3 statutory policies.'
                          : 'Standard routine triage evaluated under Section 2.4.'
                      )}
                    </p>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-700 dark:text-slate-300">3. Applicable Policy Provision:</div>
                    <p className="font-mono text-blue-700 dark:text-blue-300 font-bold mt-0.5">
                      {referral.policy_evaluation?.applicable_section || (isMinorPresent ? 'ACA-2026/2 §3.9' : 'ACA-2026/1 §2.4')}
                    </p>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-700 dark:text-slate-300">4. What happens next & who acts?</div>
                    <p className="text-slate-600 dark:text-slate-400 mt-0.5">
                      {referral.policy_evaluation?.human_action_required || (
                        isMinorPresent
                          ? 'Human caseworker in Family Services conducts direct assessment.'
                          : isAwaitingApproval
                          ? 'Supervisor reviews and decides on requested entitlement action.'
                          : 'Caseworker reviews and adopts or amends the drafted triage proposal.'
                      )}
                    </p>
                  </div>
                </div>
              </div>

              {/* Resident Household Composition & Benefit Snapshot */}
              {referral.resident_snapshot ? (
                <div className="space-y-4">
                  {/* Benefit Metadata Badges */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 rounded-lg">
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold">Benefit Code</div>
                      <div className="text-sm font-bold font-mono text-slate-900 dark:text-white">
                        {referral.resident_snapshot.benefit_code}
                      </div>
                    </div>
                    <div className="p-3 bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 rounded-lg">
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold">Monthly Award</div>
                      <div className="text-sm font-bold text-slate-900 dark:text-white">
                        £{referral.resident_snapshot.award_monthly.toFixed(2)}
                      </div>
                    </div>
                    <div className="p-3 bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 rounded-lg">
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold">Account Status</div>
                      <div className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                        {referral.resident_snapshot.status}
                      </div>
                    </div>
                    <div className="p-3 bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 rounded-lg">
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold">District Office</div>
                      <div className="text-sm font-bold text-slate-900 dark:text-white">
                        {referral.resident_snapshot.district}
                      </div>
                    </div>
                  </div>

                  {/* Household Members Table with explicit DOB & Age calculation */}
                  <div>
                    <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 flex items-center justify-between">
                      <span>Registered Household Composition & Age Audit</span>
                      <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                        {referral.resident_snapshot.household.length} registered members
                      </span>
                    </h3>
                    <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
                      <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800 text-xs text-left">
                        <thead className="bg-slate-50 dark:bg-slate-800/60 font-semibold text-slate-500 dark:text-slate-400 uppercase">
                          <tr>
                            <th className="px-4 py-2.5">Resident Name</th>
                            <th className="px-4 py-2.5">Relationship</th>
                            <th className="px-4 py-2.5">Date of Birth</th>
                            <th className="px-4 py-2.5">Calculated Age</th>
                            <th className="px-4 py-2.5">Safeguarding Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                          {referral.resident_snapshot.household.map((member, i) => {
                            const calculatedAge = getMemberAge(member);
                            const isMinor = isMemberMinor(member);
                            return (
                              <tr
                                key={i}
                                className={
                                  isMinor
                                    ? 'bg-indigo-50/50 dark:bg-indigo-950/20'
                                    : 'hover:bg-slate-50 dark:hover:bg-slate-800/30'
                                }
                              >
                                <td className="px-4 py-3 font-semibold text-slate-900 dark:text-white">
                                  {member.name}
                                </td>
                                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                                  {member.relationship}
                                </td>
                                <td className="px-4 py-3 font-mono text-slate-600 dark:text-slate-300">
                                  {member.date_of_birth}
                                </td>
                                <td className="px-4 py-3 font-bold font-mono text-slate-900 dark:text-white">
                                  {calculatedAge}
                                </td>
                                <td className="px-4 py-3">
                                  {isMinor ? (
                                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 flex items-center w-fit gap-1">
                                      <Baby className="w-3 h-3" /> Minor (&lt;18) • Triggers §3.9 Handoff
                                    </span>
                                  ) : (
                                    <span className="px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                                      Adult (18+)
                                    </span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Historical Events */}
                  {referral.resident_snapshot.events && referral.resident_snapshot.events.length > 0 && (
                    <div>
                      <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">
                        Case History Events
                      </h3>
                      <div className="border border-slate-200 dark:border-slate-800 rounded-xl divide-y divide-slate-200 dark:divide-slate-800 max-h-40 overflow-y-auto text-xs">
                        {referral.resident_snapshot.events.map((ev, i) => (
                          <div key={i} className="p-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/30 flex items-start gap-3">
                            <span className="font-mono text-slate-400 shrink-0">{ev.date}</span>
                            <div>
                              <span className="font-semibold text-slate-800 dark:text-slate-200 mr-2">
                                [{ev.type}]
                              </span>
                              <span className="text-slate-600 dark:text-slate-400">{ev.detail}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-8 text-center text-slate-400 text-xs">
                  Resident record snapshot has not yet been fetched. Run the queue to retrieve details.
                </div>
              )}
            </div>
          )}

          {/* TAB 2: SAFEGUARDS & POLICY BASIS */}
          {activeTab === 'safeguards_policy' && (
            <div className="space-y-5">
              {/* Distinct Safeguarding Gate Assessment Card */}
              <div className={`p-4 rounded-xl border space-y-2 ${
                isMinorPresent
                  ? 'bg-indigo-50/90 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-800 text-indigo-950 dark:text-indigo-200'
                  : 'bg-emerald-50/90 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-950 dark:text-emerald-200'
              }`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Baby className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    <span className="text-xs font-bold uppercase tracking-wider">
                      Under-18 Safeguarding Gate (Amendment ACA-2026/2 §3.9)
                    </span>
                  </div>
                  <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-white/80 dark:bg-slate-900/80">
                    {referral.has_under_18 === true ? 'MANDATORY HANDOFF' : 'SAFEGUARDING GATE PASSED'}
                  </span>
                </div>
                <p className="text-xs leading-relaxed">
                  {referral.has_under_18 === true
                    ? 'A resident under 18 resides in this household. Under Amendment ACA-2026/2 §3.9, automated AI processing is strictly prohibited for child safeguarding. The case is transferred directly to human caseworkers in Family Services.'
                    : 'All registered household members are confirmed age 18 or older based on verified birth dates. Routine automated triage generation is permitted under statutory guidelines.'}
                </p>
              </div>

              {/* Policy Rule & Authority Section */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase">Applicable Statutory Section</span>
                  <span className="px-2.5 py-1 text-xs font-mono font-bold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 rounded">
                    {referral.policy_evaluation?.applicable_section || 'ACA-2026/1'}
                  </span>
                </div>
                <div className="text-sm font-bold text-slate-900 dark:text-white">
                  {referral.policy_evaluation?.rule_title || 'Casework Authority Evaluation'}
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                  {referral.policy_evaluation?.rationale || 'Referral evaluated under Department Policy ACA-2026/1.'}
                </p>
              </div>

              {/* Authority & Action Matrix */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                  <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase mb-1">
                    Automated Assistant Permitted to Act
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    {referral.policy_evaluation?.triage_permitted ? (
                      <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                        <Check className="w-4 h-4" /> Yes (Permitted to draft triage note §2.4)
                      </span>
                    ) : (
                      <span className="text-xs font-bold text-rose-600 dark:text-rose-400 flex items-center gap-1">
                        <Ban className="w-4 h-4" /> No (Handoff or Supervisor Action Required)
                      </span>
                    )}
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                  <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase mb-1">
                    Human Oversight & Next Step
                  </div>
                  <div className="text-xs text-slate-700 dark:text-slate-300 mt-1">
                    {referral.policy_evaluation?.human_action_required ||
                      (isMinorPresent
                        ? 'Assigned to Family Services caseworker.'
                        : isProhibited
                        ? 'Supervisor sign-off required under Section 4.'
                        : 'Caseworker reviews and adopts drafted proposal.')}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: TRIAGE PROPOSAL */}
          {activeTab === 'agent_proposal' && (
            <div className="space-y-4">
              {/* Agent Authority & Advisory Notice */}
              <div className="p-3.5 rounded-xl bg-slate-900 text-white border border-slate-800 space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                      Advisory Triage Proposal
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">Policy ACA-2026/1 §2.4</span>
                </div>
                <p className="text-[11px] text-slate-300 leading-relaxed">
                  This triage note is a proposal for human review. It has no legal or entitlement effect until explicitly adopted or modified by an authorized caseworker.
                </p>
              </div>

              {referral.triage_note ? (
                referral.triage_note.suppression_reason ? (
                  <div className="p-5 rounded-xl bg-indigo-50/80 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 text-indigo-900 dark:text-indigo-200 space-y-2">
                    <div className="flex items-center gap-2 font-bold text-xs uppercase tracking-wider">
                      <Baby className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                      <span>Drafting Suppressed: Under-18 Safeguarding Invariant</span>
                    </div>
                    <p className="text-xs leading-relaxed">
                      {referral.triage_note.suppression_reason}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2">
                      <h4 className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400 tracking-wider">
                        Case Situation Summary
                      </h4>
                      <p className="text-xs text-slate-800 dark:text-slate-200 leading-relaxed font-sans">
                        {referral.triage_note.summary_of_situation}
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2">
                      <h4 className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400 tracking-wider">
                        Recommended Next Steps for Caseworker
                      </h4>
                      <p className="text-xs text-slate-800 dark:text-slate-200 whitespace-pre-line leading-relaxed font-sans">
                        {referral.triage_note.recommended_next_steps}
                      </p>
                    </div>
                  </div>
                )
              ) : isMinorPresent ? (
                <div className="p-6 rounded-xl bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200 dark:border-indigo-800 text-indigo-900 dark:text-indigo-200 text-xs">
                  Automated triage generation was not invoked because a minor resides in the household (ACA-2026/2 §3.9).
                </div>
              ) : isProhibited ? (
                <div className="p-6 rounded-xl bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-800 text-rose-900 dark:text-rose-200 text-xs">
                  Automated triage generation was suppressed because the requested action is prohibited under Section 3.
                </div>
              ) : (
                <div className="p-8 text-center text-slate-400 text-xs">
                  Triage proposal has not yet been generated. Run the queue to generate proposals for authorized cases.
                </div>
              )}
            </div>
          )}

          {/* TAB 4: CASE TIMELINE & AUDIT */}
          {activeTab === 'timeline_audit' && (
            <div className="space-y-5">
              <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800/40 p-3 rounded-xl border border-slate-200 dark:border-slate-800">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-700 dark:text-slate-300">
                  <FileCheck className="w-4 h-4 text-emerald-500" />
                  <span>Chronological Case Timeline</span>
                </div>
                <button
                  onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                  className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline font-medium cursor-pointer"
                >
                  {showTechnicalDetails ? 'Hide Technical Metadata' : 'Show Technical Metadata'}
                </button>
              </div>

              {/* Human-Friendly Chronological Timeline */}
              <div className="relative border-l-2 border-slate-200 dark:border-slate-800 ml-3 space-y-5 pl-4 pt-2">
                {referral.audit_logs.map((log, idx) => {
                  const ev = formatAuditEvent(log);
                  const Icon = ev.icon;
                  const isExpanded = expandedLogId === log.id || (expandedLogId === null && showTechnicalDetails);

                  return (
                    <div key={log.id || idx} className="relative group">
                      <div className="absolute -left-[23px] top-1 w-3.5 h-3.5 rounded-full bg-blue-600 border-2 border-white dark:border-slate-900" />
                      <div className="flex items-baseline justify-between text-xs mb-1">
                        <span className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                          <Icon className={`w-3.5 h-3.5 ${ev.color}`} />
                          <span>{ev.title}</span>
                        </span>
                        <span className="text-slate-400 text-[11px] font-mono">
                          {parseUTC(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 dark:text-slate-300 mb-1">
                        {ev.desc}
                      </p>
                      <div className="text-[11px] text-slate-400">
                        Actor: <strong className="font-mono text-slate-600 dark:text-slate-300">{log.actor}</strong>
                      </div>

                      {/* Expandable Technical Details */}
                      {showTechnicalDetails && (
                        <div className="mt-2 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 text-[11px] font-mono text-slate-600 dark:text-slate-300 overflow-x-auto">
                          <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">
                            Technical Payload (Step: {log.step_name} • Event: {log.event_type})
                          </div>
                          {JSON.stringify(log.details, null, 2)}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Supervisor Sign-Off Controls Footer (When Awaiting Approval) */}
        {referral.approval_request && referral.approval_request.status === 'PENDING' && isAwaitingApproval && (
          <div className="shrink-0 px-6 py-4 bg-amber-50 dark:bg-amber-950/40 border-t border-amber-200 dark:border-amber-900/60 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="text-xs font-bold text-amber-900 dark:text-amber-300 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-600" /> Supervisor Sign-Off Required (Policy ACA-2026/1 §4.1)
              </div>
              <p className="text-[11px] text-amber-800 dark:text-amber-400 mt-0.5">
                Action: <strong>{referral.approval_request.requested_action}</strong> ({referral.approval_request.applicable_section})
              </p>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="text"
                value={decisionNotes}
                onChange={(e) => setDecisionNotes(e.target.value)}
                placeholder="Supervisor decision notes..."
                className="text-xs px-3 py-2 rounded-lg border border-amber-300 dark:border-amber-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white min-w-[200px]"
              />
              <button
                onClick={() => onApprove(referral.referral_id, decisionNotes || 'Approved by Supervisor')}
                className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg shadow-xs transition-colors whitespace-nowrap cursor-pointer"
              >
                Approve Action
              </button>
              <button
                onClick={() => onReject(referral.referral_id, decisionNotes || 'Declined by Supervisor')}
                className="px-3.5 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold rounded-lg shadow-xs transition-colors whitespace-nowrap cursor-pointer"
              >
                Reject Action
              </button>
            </div>
          </div>
        )}

        {/* Policy Escalation Footer (No Action Buttons) */}
        {referral.approval_request && referral.approval_request.status === 'PENDING' && isProhibited && (
          <div className="shrink-0 px-6 py-4 bg-rose-50 dark:bg-rose-950/40 border-t border-rose-200 dark:border-rose-900/60 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="text-xs font-bold text-rose-900 dark:text-rose-300 flex items-center gap-1.5">
                <AlertOctagon className="w-4 h-4 text-rose-600" /> Policy Escalation Alert (Prohibited Action)
              </div>
              <p className="text-[11px] text-rose-800 dark:text-rose-400 mt-0.5">
                Action: <strong>{referral.approval_request.requested_action}</strong> ({referral.approval_request.applicable_section}). Automated execution is legally prohibited. Manual investigation required outside of this system.
              </p>
            </div>
          </div>
        )}

        {/* Read-Only Decision Footer (Approved/Rejected) */}
        {referral.approval_request && referral.approval_request.status !== 'PENDING' && (
          <div className={`shrink-0 px-6 py-4 border-t flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 ${
            referral.approval_request.status === 'APPROVED' 
              ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900/60'
              : 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900/60'
          }`}>
            <div>
              <div className={`text-xs font-bold flex items-center gap-1.5 ${
                referral.approval_request.status === 'APPROVED' ? 'text-emerald-900 dark:text-emerald-300' : 'text-rose-900 dark:text-rose-300'
              }`}>
                {referral.approval_request.status === 'APPROVED' ? (
                  <><Check className="w-4 h-4 text-emerald-600" /> Supervisor Approved</>
                ) : (
                  <><Ban className="w-4 h-4 text-rose-600" /> Supervisor Rejected</>
                )}
              </div>
              <p className={`text-[11px] mt-0.5 ${
                referral.approval_request.status === 'APPROVED' ? 'text-emerald-800 dark:text-emerald-400' : 'text-rose-800 dark:text-rose-400'
              }`}>
                Action: <strong>{referral.approval_request.requested_action}</strong> ({referral.approval_request.applicable_section})
              </p>
            </div>
            
            <div className={`text-[11px] p-2 rounded-lg border max-w-sm ${
                referral.approval_request.status === 'APPROVED' 
                  ? 'bg-emerald-100/50 dark:bg-emerald-900/30 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200'
                  : 'bg-rose-100/50 dark:bg-rose-900/30 border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200'
              }`}>
              <div className="font-semibold mb-0.5">Notes from {referral.approval_request.supervisor_id}:</div>
              <div className="italic">"{referral.approval_request.decision_notes}"</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
