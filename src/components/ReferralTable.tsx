import React from 'react';
import { ReferralListItem, WorkflowDisposition } from '../types';
import {
  Users,
  AlertOctagon,
  CheckCircle2,
  Clock,
  ArrowRight,
  Play,
  RotateCcw,
  Sparkles,
  Baby,
  Ban,
  PauseCircle,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';

interface ReferralTableProps {
  referrals: ReferralListItem[];
  onSelectReferral: (id: string) => void;
  onProcessReferral: (id: string) => void;
  onResumeReferral: (id: string) => void;
  onRefreshReferral: (id: string) => void;
  isProcessingId: string | null;
  isProcessingAll: boolean;
}

export const ReferralTable: React.FC<ReferralTableProps> = ({
  referrals,
  onSelectReferral,
  onProcessReferral,
  onResumeReferral,
  onRefreshReferral,
  isProcessingId,
  isProcessingAll,
}) => {
  const getDispositionBadge = (disposition: WorkflowDisposition) => {
    switch (disposition) {
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60">
            <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-600 dark:text-emerald-400" /> Ready for Review
          </span>
        );
      case 'HANDOFF':
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-800 dark:bg-indigo-950/60 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/60">
            <Baby className="w-3 h-3 mr-1 text-indigo-600 dark:text-indigo-400" /> Safeguarding Handoff
          </span>
        );
      case 'ESCALATE':
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200 dark:border-rose-800/60">
            <AlertOctagon className="w-3 h-3 mr-1 text-rose-600 dark:text-rose-400" /> Escalation Required
          </span>
        );
      case 'WAIT_FOR_APPROVAL':
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-800/60">
            <Clock className="w-3 h-3 mr-1 text-amber-600 dark:text-amber-400" /> Approval Required
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-800 dark:bg-red-950/60 dark:text-red-300 border border-red-200 dark:border-red-800/60">
            <PauseCircle className="w-3 h-3 mr-1 text-red-600 dark:text-red-400" /> Processing Paused
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
            <Clock className="w-3 h-3 mr-1" /> Awaiting Processing
          </span>
        );
    }
  };

  const getUrgencyBadge = (urgency: string) => {
    switch (urgency.toLowerCase()) {
      case 'high':
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300">
            High
          </span>
        );
      case 'low':
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
            Low
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
            Standard
          </span>
        );
    }
  };

  const getSafeguardingGateBadge = (item: ReferralListItem) => {
    if (item.workflow_disposition === 'PENDING') {
      return <span className="text-xs text-slate-400 font-mono">Unchecked</span>;
    }
    if (item.has_under_18 === true) {
      return (
        <span className="inline-flex items-center text-xs font-semibold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-200 dark:border-indigo-800">
          <Baby className="w-3.5 h-3.5 mr-1 text-indigo-600 dark:text-indigo-400" /> Minor in Household (&lt;18)
        </span>
      );
    }
    if (item.has_under_18 === false) {
      return (
        <span className="inline-flex items-center text-xs text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800">
          <ShieldCheck className="w-3.5 h-3.5 mr-1 text-emerald-600 dark:text-emerald-400" /> Gate Passed (Adults Only)
        </span>
      );
    }
    return (
      <span className="inline-flex items-center text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 rounded border border-amber-200 dark:border-amber-800">
        <AlertTriangle className="w-3.5 h-3.5 mr-1" /> Unresolved (Fail-Safe)
      </span>
    );
  };

  const getAgentTriageBadge = (item: ReferralListItem) => {
    if (item.workflow_disposition === 'PENDING') {
      return <span className="text-xs text-slate-400 font-mono">Pending Run</span>;
    }
    if (item.has_under_18 === true) {
      return (
        <span className="inline-flex items-center text-xs font-semibold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-200 dark:border-indigo-800">
          <Baby className="w-3 h-3 mr-1 text-indigo-500" /> Blocked (§3.9 Gate)
        </span>
      );
    }
    if (item.workflow_disposition === 'ESCALATE') {
      return (
        <span className="inline-flex items-center text-xs font-semibold text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40 px-2 py-0.5 rounded border border-rose-200 dark:border-rose-800">
          <Ban className="w-3 h-3 mr-1 text-rose-500" /> Suppressed (Section 3)
        </span>
      );
    }
    if (item.triage_drafted) {
      return (
        <span className="inline-flex items-center text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800">
          <Sparkles className="w-3 h-3 mr-1 text-emerald-500" /> Proposal Drafted
        </span>
      );
    }
    if (item.workflow_disposition === 'WAIT_FOR_APPROVAL') {
      return (
        <span className="inline-flex items-center text-xs font-semibold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 rounded border border-amber-200 dark:border-amber-800">
          <Clock className="w-3 h-3 mr-1 text-amber-500" /> Drafted (Needs Sign-Off)
        </span>
      );
    }
    return <span className="text-xs text-slate-400 font-mono">—</span>;
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800 text-left">
          <thead className="bg-slate-50 dark:bg-slate-800/50 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            <tr>
              <th scope="col" className="px-4 py-3.5">Referral & Urgency</th>
              <th scope="col" className="px-4 py-3.5">Resident Reference</th>
              <th scope="col" className="px-4 py-3.5">Requested Action</th>
              <th scope="col" className="px-4 py-3.5">Under-18 Safeguarding Gate</th>
              <th scope="col" className="px-4 py-3.5">Statutory Policy</th>
              <th scope="col" className="px-4 py-3.5">Agent Triage Status</th>
              <th scope="col" className="px-4 py-3.5">Workflow Disposition</th>
              <th scope="col" className="px-4 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-sm">
            {referrals.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-6 py-12 text-center text-slate-500 dark:text-slate-400">
                  No referrals found matching current criteria.
                </td>
              </tr>
            ) : (
              referrals.map((item) => {
                const isItemProcessing = isProcessingId === item.referral_id;

                return (
                  <tr
                    key={item.referral_id}
                    className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="px-4 py-4 whitespace-nowrap">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono font-semibold text-slate-900 dark:text-white">
                          {item.referral_id}
                        </span>
                        {getUrgencyBadge(item.urgency)}
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 font-mono">
                        {new Date(item.received_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </div>
                    </td>

                    <td className="px-4 py-4">
                      <div className="font-medium text-slate-800 dark:text-slate-200 font-mono">
                        {item.resident_ref}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-slate-400 truncate max-w-[150px]">
                        {item.source}
                      </div>
                    </td>

                    <td className="px-4 py-4 max-w-xs">
                      <div className="font-medium text-slate-900 dark:text-slate-100 truncate">
                        {item.requested_action}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">
                        {item.summary}
                      </div>
                    </td>

                    <td className="px-4 py-4 whitespace-nowrap">
                      {getSafeguardingGateBadge(item)}
                    </td>

                    <td className="px-4 py-4 whitespace-nowrap">
                      {item.applicable_section ? (
                        <span className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">
                          {item.applicable_section}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400 font-mono">—</span>
                      )}
                    </td>

                    <td className="px-4 py-4 whitespace-nowrap">
                      {getAgentTriageBadge(item)}
                    </td>

                    <td className="px-4 py-4 whitespace-nowrap">
                      {getDispositionBadge(item.workflow_disposition)}
                    </td>

                    <td className="px-4 py-4 whitespace-nowrap text-right text-xs font-medium space-x-1.5">
                      {item.workflow_disposition === 'PENDING' && (
                        <button
                          onClick={() => onProcessReferral(item.referral_id)}
                          disabled={isItemProcessing}
                          className="px-2.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-md shadow-xs transition-colors inline-flex items-center gap-1 disabled:opacity-50 cursor-pointer"
                        >
                          <Play className="w-3 h-3" />
                          <span>Run</span>
                        </button>
                      )}

                      <button
                        onClick={() => onSelectReferral(item.referral_id)}
                        className="px-3 py-1.5 bg-slate-900 dark:bg-slate-700 hover:bg-slate-800 dark:hover:bg-slate-600 text-white rounded-md shadow-xs transition-colors inline-flex items-center gap-1 cursor-pointer"
                      >
                        <span>Review Case</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
