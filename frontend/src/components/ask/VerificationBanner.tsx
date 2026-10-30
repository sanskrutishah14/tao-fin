import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { Verification } from '../../types/api';

interface VerificationBannerProps {
  verification?: Verification;
  isDeclined?: boolean;
}

export const VerificationBanner: React.FC<VerificationBannerProps> = ({
  verification,
  isDeclined = false,
}) => {
  const [detailsOpen, setDetailsOpen] = useState(false);

  if (!verification && !isDeclined) return null;

  const checks = verification?.checks || {};
  const failedChecks = verification?.failed_checks || [];
  const hasFailures =
    failedChecks.length > 0 ||
    checks.numerical === false ||
    checks.evidence === false ||
    checks.logical === false ||
    checks.financial_consistency === false;

  if (isDeclined) {
    return (
      <div className="bg-amber-50/80 dark:bg-amber-950/40 border border-amber-200/90 dark:border-amber-800/80 rounded-2xl p-4 flex items-center justify-between text-amber-900 dark:text-amber-200 transition-all">
        <div className="flex items-center space-x-2.5">
          <div className="w-5 h-5 rounded-full bg-amber-500 text-white flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-3.5 h-3.5" />
          </div>
          <span className="text-sm font-semibold">
            Declined to answer — insufficient verified filing evidence.
          </span>
        </div>
      </div>
    );
  }

  if (hasFailures) {
    return (
      <div className="bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/80 rounded-2xl p-4 text-rose-900 dark:text-rose-200 transition-all">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-5 h-5 rounded-full bg-rose-600 text-white flex items-center justify-center flex-shrink-0">
              <XCircle className="w-3.5 h-3.5" />
            </div>
            <span className="text-sm font-semibold">
              Verification check failed against filing evidence.
            </span>
          </div>

          <button
            type="button"
            onClick={() => setDetailsOpen(!detailsOpen)}
            className="text-xs text-rose-700 dark:text-rose-300 hover:text-rose-900 dark:hover:text-rose-100 font-medium flex items-center space-x-1"
          >
            <span>Details</span>
            {detailsOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        {detailsOpen && (
          <div className="mt-3 pt-3 border-t border-rose-200/70 dark:border-rose-800/70 text-xs space-y-1.5">
            <div className="font-semibold text-rose-950 dark:text-rose-100">Verification check results:</div>
            <div className="grid grid-cols-2 gap-2 mt-1">
              <div className="flex items-center space-x-1.5">
                <span>Numerical:</span>
                <span className={checks.numerical ? 'text-emerald-700 dark:text-emerald-400 font-semibold' : 'text-rose-700 dark:text-rose-400 font-semibold'}>
                  {checks.numerical ? 'Pass' : 'Fail'}
                </span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span>Evidence:</span>
                <span className={checks.evidence ? 'text-emerald-700 dark:text-emerald-400 font-semibold' : 'text-rose-700 dark:text-rose-400 font-semibold'}>
                  {checks.evidence ? 'Pass' : 'Fail'}
                </span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span>Logical:</span>
                <span className={checks.logical ? 'text-emerald-700 dark:text-emerald-400 font-semibold' : 'text-rose-700 dark:text-rose-400 font-semibold'}>
                  {checks.logical ? 'Pass' : 'Fail'}
                </span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span>Financial:</span>
                <span className={checks.financial_consistency ? 'text-emerald-700 dark:text-emerald-400 font-semibold' : 'text-rose-700 dark:text-rose-400 font-semibold'}>
                  {checks.financial_consistency ? 'Pass' : 'Fail'}
                </span>
              </div>
            </div>
            {failedChecks.length > 0 && (
              <div className="mt-2 text-rose-800 dark:text-rose-300">
                Failed checks: {failedChecks.join(', ')}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-emerald-50/70 dark:bg-emerald-950/40 border border-emerald-200/80 dark:border-emerald-800/80 rounded-2xl p-4 flex items-center justify-between text-emerald-900 dark:text-emerald-200 shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors duration-200">
      <div className="flex items-center space-x-2.5">
        <div className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center flex-shrink-0">
          <CheckCircle2 className="w-3.5 h-3.5" />
        </div>
        <span className="text-sm font-semibold text-emerald-900 dark:text-emerald-200">
          Verified against filing evidence.
        </span>
      </div>

      <span className="text-xs text-emerald-700 dark:text-emerald-400 font-medium hidden sm:inline-block">
        Deterministic cross-check passed
      </span>
    </div>
  );
};
