import React from 'react';
import {
  ShieldAlert,
  Play,
  RotateCcw,
  CheckCircle2,
  Sun,
  Moon,
  RefreshCw,
} from 'lucide-react';

interface HeaderProps {
  onProcessAll: () => void;
  onAutoRunSequential: () => void;
  onRefresh: () => void;
  isProcessing: boolean;
  isRefreshing: boolean;
  processingProgress?: { current: number; total: number; currentId?: string } | null;
  darkMode: boolean;
  onToggleTheme: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onProcessAll,
  onAutoRunSequential,
  onRefresh,
  isProcessing,
  isRefreshing,
  processingProgress,
  darkMode,
  onToggleTheme,
}) => {
  return (
    <header className="bg-white dark:bg-slate-900 text-slate-900 dark:text-white border-b border-slate-200 dark:border-slate-800 sticky top-0 z-30 shadow-xs transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3.5">
          {/* Logo & Operational Identity */}
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-blue-50 dark:bg-blue-600/20 text-blue-600 dark:text-blue-400 rounded-xl border border-blue-200 dark:border-blue-500/30 flex items-center justify-center">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2 flex-wrap">
                <h1 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">
                  Brite Casework Assistant
                </h1>
                <span className="px-2 py-0.5 text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30 rounded-full flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Safeguarding Gate Active (ACA-2026/2 §3.9)
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Calder County Dept of Household Services • Casework & Triage Console
              </p>
            </div>
          </div>

          {/* Action & Navigation Controls */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Light / Dark Mode Toggle */}
            <button
              onClick={onToggleTheme}
              title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
              className="p-2 text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 rounded-lg transition-colors flex items-center justify-center"
              aria-label="Toggle Theme"
            >
              {darkMode ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-700" />}
            </button>

            <button
              onClick={onRefresh}
              disabled={isProcessing || isRefreshing}
              title="Refresh database state"
              className="px-3 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''} ${isProcessing ? 'opacity-50' : ''}`} />
              <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
            </button>

            <button
              onClick={onAutoRunSequential}
              disabled={isProcessing}
              className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 active:bg-blue-700 rounded-lg shadow-xs transition-all flex items-center gap-2 disabled:opacity-50 cursor-pointer"
            >
              <Play className={`w-3.5 h-3.5 ${isProcessing ? 'animate-spin' : ''}`} />
              <span>
                {isProcessing
                  ? processingProgress
                    ? `Processing ${processingProgress.current}/${processingProgress.total}...`
                    : 'Processing Queue...'
                  : 'Run Morning Queue'}
              </span>
            </button>
          </div>
        </div>

        {/* Live Processing Progress Bar if Active */}
        {isProcessing && processingProgress && (
          <div className="mt-3 pt-2.5 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
            <div className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-ping" />
              <span>
                Processing referral: <strong className="text-slate-900 dark:text-white font-mono">{processingProgress.currentId || '...'}</strong> ({processingProgress.current} of {processingProgress.total})
              </span>
            </div>
            <div className="w-32 bg-slate-200 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
              <div
                className="bg-blue-600 dark:bg-blue-500 h-2 transition-all duration-300 rounded-full"
                style={{
                  width: `${(processingProgress.current / processingProgress.total) * 100}%`,
                }}
              />
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
