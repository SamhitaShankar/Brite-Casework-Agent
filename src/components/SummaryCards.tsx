import React from 'react';
import { QueueSummary } from '../types';
import {
  CheckCircle,
  Clock,
  Inbox,
  Baby,
  AlertOctagon,
  Shield,
  ShieldAlert,
  PauseCircle,
  HelpCircle,
} from 'lucide-react';

interface SummaryCardsProps {
  summary: QueueSummary;
  selectedFilter: string | null;
  onSelectFilter: (filter: string | null) => void;
}

export const SummaryCards: React.FC<SummaryCardsProps> = ({
  summary,
  selectedFilter,
  onSelectFilter,
}) => {
  const humanAuthorityRequired =
    summary.handed_off + summary.escalated + summary.awaiting_approval + summary.failed;

  const cards = [
    {
      id: null,
      title: 'Total Intake',
      count: summary.total_referrals,
      icon: Inbox,
      color: 'text-slate-700 bg-slate-100 dark:text-slate-300 dark:bg-slate-800',
      activeColor: 'ring-2 ring-slate-400 bg-slate-50 dark:bg-slate-800/80',
      subtitle: `${summary.pending} awaiting processing`,
    },
    {
      id: 'COMPLETED',
      title: 'Ready for Review',
      count: summary.completed,
      icon: CheckCircle,
      color: 'text-emerald-700 bg-emerald-100 dark:text-emerald-300 dark:bg-emerald-950/40',
      activeColor: 'ring-2 ring-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/60',
      subtitle: 'Triage proposal drafted (§2.4)',
    },
    {
      id: 'HANDOFF',
      title: 'Safeguarding Handoff',
      count: summary.handed_off,
      icon: Baby,
      color: 'text-indigo-700 bg-indigo-100 dark:text-indigo-300 dark:bg-indigo-950/40',
      activeColor: 'ring-2 ring-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/60',
      subtitle: 'Minor in household (ACA-2026/2 §3.9)',
    },
    {
      id: 'ESCALATE',
      title: 'Escalation Required',
      count: summary.escalated,
      icon: AlertOctagon,
      color: 'text-rose-700 bg-rose-100 dark:text-rose-300 dark:bg-rose-950/40',
      activeColor: 'ring-2 ring-rose-500 bg-rose-50/50 dark:bg-rose-950/60',
      subtitle: 'Section 3 statutory prohibition',
    },
    {
      id: 'WAIT_FOR_APPROVAL',
      title: 'Supervisor Approval',
      count: summary.awaiting_approval,
      icon: Clock,
      color: 'text-amber-700 bg-amber-100 dark:text-amber-300 dark:bg-amber-950/40',
      activeColor: 'ring-2 ring-amber-500 bg-amber-50/50 dark:bg-amber-950/60',
      subtitle: 'Human sign-off required',
    },
  ];

  return (
    <div className="space-y-4 my-6">
      {/* Primary Queue Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {cards.map((card) => {
          const Icon = card.icon;
          const isSelected = selectedFilter === card.id;

          return (
            <button
              key={card.title}
              onClick={() => onSelectFilter(isSelected ? null : card.id)}
              className={`text-left p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs transition-all hover:shadow-md cursor-pointer ${
                isSelected ? card.activeColor : ''
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                  {card.title}
                </span>
                <div className={`p-1.5 rounded-lg ${card.color}`}>
                  <Icon className="w-4 h-4" />
                </div>
              </div>
              <div className="flex items-baseline space-x-2">
                <span className="text-2xl font-bold text-slate-900 dark:text-white">
                  {card.count}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 truncate">
                {card.subtitle}
              </p>
            </button>
          );
        })}
      </div>

      {/* Casework Oversight & Safeguarding Notice Banner */}
      <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 transition-colors">
        <div className="flex items-start space-x-3.5">
          <div className="p-2.5 bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400 rounded-xl border border-blue-200 dark:border-blue-800/60 shrink-0">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2 flex-wrap gap-y-1">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                Casework Safeguarding & Oversight
              </span>
              <span className="px-2 py-0.5 text-[11px] font-semibold bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200 rounded-full border border-blue-200 dark:border-blue-800">
                {humanAuthorityRequired} of {summary.total_referrals} cases flagged for human decision
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 max-w-2xl leading-relaxed">
              Automated assistance strictly respects Department authority limits. Referrals involving children under 18, benefit adjustments, payment details, or policy escalation are automatically routed to caseworkers and supervisors.
            </p>
          </div>
        </div>

        {/* Interactive Casework Status Badges */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <button
            onClick={() => onSelectFilter(selectedFilter === 'HANDOFF' ? null : 'HANDOFF')}
            className={`px-3 py-1.5 rounded-lg border transition-all cursor-pointer flex items-center gap-1.5 ${
              selectedFilter === 'HANDOFF'
                ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                : 'bg-white dark:bg-slate-800 text-indigo-800 dark:text-indigo-300 border-indigo-200 dark:border-slate-700 hover:bg-indigo-50 dark:hover:bg-slate-750'
            }`}
            title="Filter to cases transferred for child safeguarding"
          >
            <Baby className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" />
            <span>Child in Home (&lt;18): <strong>{summary.handed_off}</strong></span>
          </button>

          <button
            onClick={() => onSelectFilter(selectedFilter === 'ESCALATE' ? null : 'ESCALATE')}
            className={`px-3 py-1.5 rounded-lg border transition-all cursor-pointer flex items-center gap-1.5 ${
              selectedFilter === 'ESCALATE'
                ? 'bg-rose-600 text-white border-rose-600 shadow-xs'
                : 'bg-white dark:bg-slate-800 text-rose-800 dark:text-rose-300 border-rose-200 dark:border-slate-700 hover:bg-rose-50 dark:hover:bg-slate-750'
            }`}
            title="Filter to cases escalated under Section 3"
          >
            <AlertOctagon className="w-3.5 h-3.5 text-rose-500 dark:text-rose-400" />
            <span>Policy Escalation: <strong>{summary.escalated}</strong></span>
          </button>

          <button
            onClick={() => onSelectFilter(selectedFilter === 'WAIT_FOR_APPROVAL' ? null : 'WAIT_FOR_APPROVAL')}
            className={`px-3 py-1.5 rounded-lg border transition-all cursor-pointer flex items-center gap-1.5 ${
              selectedFilter === 'WAIT_FOR_APPROVAL'
                ? 'bg-amber-600 text-white border-amber-600 shadow-xs'
                : 'bg-white dark:bg-slate-800 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-slate-700 hover:bg-amber-50 dark:hover:bg-slate-750'
            }`}
            title="Filter to cases awaiting supervisor sign-off"
          >
            <Clock className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400" />
            <span>Supervisor Sign-Off: <strong>{summary.awaiting_approval}</strong></span>
          </button>

          {summary.failed > 0 && (
            <span className="px-3 py-1.5 rounded-lg bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800/60 flex items-center gap-1.5">
              <PauseCircle className="w-3.5 h-3.5 text-red-500" />
              <span>Paused: <strong>{summary.failed}</strong></span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
