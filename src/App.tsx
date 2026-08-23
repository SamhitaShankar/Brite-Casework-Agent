import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { SummaryCards } from './components/SummaryCards';
import { ReferralTable } from './components/ReferralTable';
import { CaseDetailModal } from './components/CaseDetailModal';
import { ReferralListItem, ReferralDetail, QueueSummary } from './types';
import {
  AlertCircle,
  RefreshCw,
  Clock,
  ArrowRight,
  Play,
  RotateCcw,
  Sparkles,
  Inbox,
  Lock,
} from 'lucide-react';

export function App() {
  const [referrals, setReferrals] = useState<ReferralListItem[]>([]);
  const [summary, setSummary] = useState<QueueSummary>({
    total_referrals: 0,
    completed: 0,
    handed_off: 0,
    escalated: 0,
    awaiting_approval: 0,
    pending: 0,
    failed: 0,
  });
  const [selectedFilter, setSelectedFilter] = useState<string | null>(null);
  const [selectedReferralId, setSelectedReferralId] = useState<string | null>(null);
  const [selectedReferralDetail, setSelectedReferralDetail] = useState<ReferralDetail | null>(null);
  const [isProcessingAll, setIsProcessingAll] = useState(false);
  const [processingProgress, setProcessingProgress] = useState<{
    current: number;
    total: number;
    currentId?: string;
  } | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Theme management (Light / Dark mode)
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    const saved = localStorage.getItem('brite_theme');
    if (saved) return saved === 'dark';
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('brite_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('brite_theme', 'light');
    }
  }, [darkMode]);

  const toggleTheme = () => {
    setDarkMode((prev) => !prev);
  };

  // Load initial data from backend
  const fetchData = async () => {
    setIsRefreshing(true);
    try {
      const [refRes, sumRes] = await Promise.all([
        fetch('/api/referrals'),
        fetch('/api/queue/summary'),
      ]);

      if (refRes.ok && sumRes.ok) {
        const refData = await refRes.json();
        const sumData = await sumRes.json();
        setReferrals(refData);
        setSummary(sumData);
        setErrorMessage(null);
      }
      
      // Add a tiny artificial delay so the user can visually confirm the refresh happened
      await new Promise(resolve => setTimeout(resolve, 300));
    } catch (e: any) {
      console.error('Error fetching data:', e);
      setErrorMessage('Could not connect to the backend service. Please verify server connectivity.');
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Fetch single detail when modal is opened
  const fetchReferralDetail = async (id: string) => {
    try {
      const res = await fetch(`/api/referrals/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedReferralDetail(data);
      }
    } catch (e) {
      console.error('Error fetching detail:', e);
    }
  };

  const handleSelectReferral = (id: string) => {
    setSelectedReferralId(id);
    fetchReferralDetail(id);
  };

  const handleCloseModal = () => {
    setSelectedReferralId(null);
    setSelectedReferralDetail(null);
  };

  // Run single referral
  const handleProcessReferral = async (id: string) => {
    setProcessingId(id);
    try {
      const res = await fetch(`/api/referrals/${id}/process`, { method: 'POST' });
      if (res.ok) {
        await fetchData();
        if (selectedReferralId === id) {
          await fetchReferralDetail(id);
        }
      }
    } catch (e) {
      console.error('Error processing single referral:', e);
    } finally {
      setProcessingId(null);
    }
  };

  // Resume single referral
  const handleResumeReferral = async (id: string) => {
    setProcessingId(id);
    try {
      const res = await fetch(`/api/referrals/${id}/resume`, { method: 'POST' });
      if (res.ok) {
        await fetchData();
        if (selectedReferralId === id) {
          await fetchReferralDetail(id);
        }
      }
    } catch (e) {
      console.error('Error resuming referral:', e);
    } finally {
      setProcessingId(null);
    }
  };

  // Process all queue batch
  const handleProcessAll = async () => {
    setIsProcessingAll(true);
    try {
      const res = await fetch('/api/referrals/process-all', { method: 'POST' });
      if (res.ok) {
        await fetchData();
      }
    } catch (e) {
      console.error('Error processing all queue:', e);
    } finally {
      setIsProcessingAll(false);
    }
  };

  // Sequential Live Queue Runner (Visibly steps through each case via real backend endpoints)
  const handleAutoRunSequential = async () => {
    setIsProcessingAll(true);
    try {
      const refRes = await fetch('/api/referrals');
      if (!refRes.ok) return;
      const currentList: ReferralListItem[] = await refRes.json();
      const pendingOrAll = currentList.filter((r) => r.workflow_disposition === 'PENDING');
      const queueToRun = pendingOrAll.length > 0 ? pendingOrAll : currentList;

      for (let i = 0; i < queueToRun.length; i++) {
        const item = queueToRun[i];
        setProcessingProgress({
          current: i + 1,
          total: queueToRun.length,
          currentId: item.referral_id,
        });
        setProcessingId(item.referral_id);

        try {
          await fetch(`/api/referrals/${item.referral_id}/process`, { method: 'POST' });
        } catch (err) {
          console.error(`Error processing ${item.referral_id}:`, err);
        }

        // Live refresh state after each processed referral
        await fetchData();
      }
    } catch (e) {
      console.error('Error running sequential queue:', e);
    } finally {
      setIsProcessingAll(false);
      setProcessingProgress(null);
      setProcessingId(null);
    }
  };



  // Approve supervisor action
  const handleApprove = async (referralId: string, notes: string) => {
    try {
      const res = await fetch(`/api/referrals/${referralId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision_notes: notes, supervisor_id: 'SUP-01' }),
      });
      if (res.ok) {
        await fetchData();
        await fetchReferralDetail(referralId);
      }
    } catch (e) {
      console.error('Error approving request:', e);
    }
  };

  // Reject supervisor action
  const handleReject = async (referralId: string, notes: string) => {
    try {
      const res = await fetch(`/api/referrals/${referralId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision_notes: notes, supervisor_id: 'SUP-01' }),
      });
      if (res.ok) {
        await fetchData();
        await fetchReferralDetail(referralId);
      }
    } catch (e) {
      console.error('Error rejecting request:', e);
    }
  };

  // Filtered referrals list
  const filteredReferrals = referrals.filter((item) => {
    if (!selectedFilter) return true;
    return item.workflow_disposition === selectedFilter;
  });

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors">
      <Header
        onProcessAll={handleProcessAll}
        onAutoRunSequential={handleAutoRunSequential}
        onRefresh={fetchData}
        isProcessing={isProcessingAll}
        isRefreshing={isRefreshing}
        processingProgress={processingProgress}
        darkMode={darkMode}
        onToggleTheme={toggleTheme}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {errorMessage && (
          <div className="mb-6 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <p className="text-sm">{errorMessage}</p>
          </div>
        )}

        {/* Live Morning Operations Intake Banner (When queue is in initial/reset un-processed state) */}
        {summary.pending === summary.total_referrals && summary.total_referrals > 0 && (
          <div className="mb-6 p-4 rounded-xl bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/60 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-blue-900 dark:text-blue-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-blue-600 text-white rounded-lg">
                <Inbox className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold">
                  Morning Queue Received • 12 Referrals Awaiting Processing
                </h3>
                <p className="text-xs text-blue-700 dark:text-blue-300 mt-0.5">
                  Click <strong>Run Morning Queue</strong> to step through the overnight queue and evaluate each case against safeguarding gates and statutory policy.
                </p>
              </div>
            </div>
            <button
              onClick={handleAutoRunSequential}
              disabled={isProcessingAll}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg shadow-xs flex items-center gap-1.5 transition-colors whitespace-nowrap self-start sm:self-auto cursor-pointer"
            >
              <Play className="w-3.5 h-3.5" />
              <span>Start Morning Run</span>
            </button>
          </div>
        )}

        {/* Supervisor Review Alert Banner */}
        {summary.awaiting_approval > 0 && (
          <div className="mb-6 p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-amber-900 dark:text-amber-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-amber-500 text-white rounded-lg">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold flex items-center gap-1.5">
                  <span>Supervisor Approval Required</span>
                  <span className="px-2 py-0.5 text-[11px] font-mono bg-amber-200 dark:bg-amber-900 text-amber-900 dark:text-amber-100 rounded-full font-bold">
                    {summary.awaiting_approval} case{summary.awaiting_approval === 1 ? '' : 's'}
                  </span>
                </h3>
                <p className="text-xs text-amber-700 dark:text-amber-300 mt-0.5">
                  Statutory Rule ACA-2026/1 §4.1: Human supervisor sign-off is mandatory before any benefit or entitlement change.
                </p>
              </div>
            </div>
            <button
              onClick={() => setSelectedFilter('WAIT_FOR_APPROVAL')}
              className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold rounded-lg shadow-xs flex items-center gap-1.5 transition-colors whitespace-nowrap self-start sm:self-auto cursor-pointer"
            >
              <span>Review Sign-Offs</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Top Summary Metrics & Authority Boundary Card */}
        <SummaryCards
          summary={summary}
          selectedFilter={selectedFilter}
          onSelectFilter={setSelectedFilter}
        />

        {/* Referrals Table Section */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-bold text-slate-900 dark:text-white">
                Intake Referrals Queue
              </h2>
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                ({filteredReferrals.length} {selectedFilter ? `filtered by ${selectedFilter}` : 'total'})
              </span>
              {selectedFilter && (
                <button
                  onClick={() => setSelectedFilter(null)}
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium ml-2 cursor-pointer"
                >
                  Clear Filter
                </button>
              )}
            </div>

            <button
              onClick={fetchData}
              disabled={isProcessingAll || isRefreshing}
              className="text-xs text-slate-500 hover:text-slate-900 dark:hover:text-white flex items-center gap-1 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
              <span>{isRefreshing ? 'Refreshing...' : 'Refresh Queue'}</span>
            </button>
          </div>

          <ReferralTable
            referrals={filteredReferrals}
            onSelectReferral={handleSelectReferral}
            onProcessReferral={handleProcessReferral}
            onResumeReferral={handleResumeReferral}
            onRefreshReferral={fetchData}
            isProcessingId={processingId}
            isProcessingAll={isProcessingAll}
          />
        </div>
      </main>

      {/* Case Detail Modal / Drawer with Decision Explanation & Audit */}
      <CaseDetailModal
        referral={selectedReferralDetail}
        onClose={handleCloseModal}
        onApprove={handleApprove}
        onReject={handleReject}
        onResume={handleResumeReferral}
      />
    </div>
  );
}

export default App;
