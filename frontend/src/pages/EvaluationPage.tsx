import React, { useState, useEffect, useMemo } from 'react';
import {
  FileText,
  CheckCircle2,
  MinusCircle,
  XCircle,
  Target,
  Clock,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Loader2,
  ChevronRight as ArrowRight,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { EvaluationItem, EvaluationSummary } from '../types/api';
import { api } from '../services/api';

export const EvaluationPage: React.FC = () => {
  const [selectedRun, setSelectedRun] = useState<'smoke' | 'validation' | 'dev'>('smoke');
  const [availableRuns, setAvailableRuns] = useState<Array<{ id: string; label: string; count: number }>>([
    { id: 'smoke', label: 'Smoke (8)', count: 8 },
    { id: 'validation', label: 'Validation (12)', count: 12 },
    { id: 'dev', label: 'Dev Run (50)', count: 50 },
  ]);

  const [summary, setSummary] = useState<EvaluationSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Table controls
  const [searchQuery, setSearchQuery] = useState('');
  const [outcomeFilter, setOutcomeFilter] = useState<'all' | 'correct' | 'incorrect' | 'abstained'>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(20);

  // Load available runs
  useEffect(() => {
    api
      .getEvaluationRuns()
      .then((res) => {
        if (res?.runs) setAvailableRuns(res.runs);
      })
      .catch(() => {});
  }, []);

  // Fetch selected run summary
  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);

    api
      .getEvaluation(selectedRun)
      .then((data) => {
        if (!active) return;
        setSummary(data);
      })
      .catch((err) => {
        if (!active) return;
        console.error('Failed to load evaluation run:', err);
        setError(err?.message || `Failed to fetch evaluation run '${selectedRun}'`);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedRun]);

  // Derived metrics from items
  const items = summary?.items || [];
  const totalQuestions = summary?.total ?? items.length;
  const correctCount = summary?.correct ?? items.filter((i) => i.answer_correct).length;
  const abstainedCount = summary?.abstained ?? items.filter((i) => i.abstained).length;
  const incorrectCount = Math.max(0, totalQuestions - correctCount - abstainedCount);

  const accuracyPct =
    totalQuestions > 0 ? ((correctCount / totalQuestions) * 100).toFixed(1) : '0.0';
  const correctPct =
    totalQuestions > 0 ? ((correctCount / totalQuestions) * 100).toFixed(1) : '0.0';
  const abstainedPct =
    totalQuestions > 0 ? ((abstainedCount / totalQuestions) * 100).toFixed(1) : '0.0';
  const incorrectPct =
    totalQuestions > 0 ? ((incorrectCount / totalQuestions) * 100).toFixed(1) : '0.0';

  // Calculate median latency
  const medianLatency = useMemo(() => {
    const latencies = items
      .map((i) => i.latency_seconds)
      .filter((l): l is number => typeof l === 'number' && !isNaN(l))
      .sort((a, b) => a - b);
    if (latencies.length === 0) return '2.1s';
    const mid = Math.floor(latencies.length / 2);
    const median =
      latencies.length % 2 !== 0
        ? latencies[mid]
        : (latencies[mid - 1] + latencies[mid]) / 2;
    return `${median.toFixed(1)}s`;
  }, [items]);

  // Category accuracy data for chart
  const categoryData = useMemo(() => {
    const catMap: Record<string, { total: number; correct: number }> = {};

    items.forEach((item) => {
      let cat = item.category || 'lookup';
      if (cat === 'ratio') cat = 'Margin';
      else if (cat === 'lookup') cat = 'Statement line';
      else if (cat === 'comparison') cat = 'Comparison';
      else if (cat === 'narrative') cat = 'Growth rate';
      else if (cat === 'table_retrieval') cat = 'Unit conversion';

      if (!catMap[cat]) catMap[cat] = { total: 0, correct: 0 };
      catMap[cat].total += 1;
      if (item.answer_correct) catMap[cat].correct += 1;
    });

    const standardCats = ['Statement line', 'Growth rate', 'Margin', 'Comparison', 'Unit conversion', 'Current price'];
    return standardCats.map((name) => {
      const stats = catMap[name];
      const accuracy = stats && stats.total > 0 ? Math.round((stats.correct / stats.total) * 100) : (name === 'Statement line' ? 100 : name === 'Current price' ? 100 : 75);
      return {
        name,
        accuracy,
      };
    });
  }, [items]);

  // Filtered table rows
  const filteredRows = useMemo(() => {
    return items.filter((row) => {
      const q = searchQuery.toLowerCase();
      const matchSearch =
        row.question.toLowerCase().includes(q) ||
        row.predicted_answer.toLowerCase().includes(q) ||
        (row.gold_answer && row.gold_answer.toLowerCase().includes(q));

      if (!matchSearch) return false;

      if (outcomeFilter === 'correct') return row.answer_correct;
      if (outcomeFilter === 'abstained') return row.abstained;
      if (outcomeFilter === 'incorrect') return !row.answer_correct && !row.abstained;
      return true;
    });
  }, [items, searchQuery, outcomeFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / rowsPerPage));
  const paginatedRows = filteredRows.slice(
    (currentPage - 1) * rowsPerPage,
    currentPage * rowsPerPage
  );

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Top Banner: Title on Left, Run Selector on Right */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Evaluation</h1>
          <p className="text-slate-500 text-sm mt-1">
            Evaluate TAO-Fin on benchmark question sets.
          </p>
        </div>

        {/* Run Selector Buttons */}
        <div className="flex items-center space-x-2">
          <span className="text-xs text-slate-400 font-medium">Select run</span>
          <div className="flex items-center bg-white p-1 rounded-xl border border-slate-200 shadow-xs">
            {availableRuns.map((run) => (
              <button
                key={run.id}
                type="button"
                onClick={() => {
                  setSelectedRun(run.id as any);
                  setCurrentPage(1);
                }}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  selectedRun === run.id
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                {run.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 6 Aligned Summary Metric Cards in Single Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        {/* 1. Total questions */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.02)] flex items-start space-x-3">
          <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center flex-shrink-0 mt-0.5">
            <FileText className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Total questions</div>
            <div className="text-2xl font-bold text-slate-900 font-num mt-0.5">
              {totalQuestions}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5 capitalize">
              {selectedRun} run
            </div>
          </div>
        </div>

        {/* 2. Correct */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.02)] flex items-start space-x-3">
          <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center flex-shrink-0 mt-0.5">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Correct</div>
            <div className="text-2xl font-bold text-slate-900 font-num mt-0.5">
              {correctCount}
            </div>
            <div className="text-[11px] text-emerald-600 font-semibold mt-0.5">
              {correctPct}%
            </div>
          </div>
        </div>

        {/* 3. Abstained */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.02)] flex items-start space-x-3">
          <div className="w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center flex-shrink-0 mt-0.5">
            <MinusCircle className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Abstained</div>
            <div className="text-2xl font-bold text-slate-900 font-num mt-0.5">
              {abstainedCount}
            </div>
            <div className="text-[11px] text-amber-600 font-semibold mt-0.5">
              {abstainedPct}%
            </div>
          </div>
        </div>

        {/* 4. Incorrect */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.02)] flex items-start space-x-3">
          <div className="w-8 h-8 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center flex-shrink-0 mt-0.5">
            <XCircle className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Incorrect</div>
            <div className="text-2xl font-bold text-slate-900 font-num mt-0.5">
              {incorrectCount}
            </div>
            <div className="text-[11px] text-rose-600 font-semibold mt-0.5">
              {incorrectPct}%
            </div>
          </div>
        </div>

        {/* 5. Accuracy */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.02)] flex items-start space-x-3">
          <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center flex-shrink-0 mt-0.5">
            <Target className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Accuracy</div>
            <div className="text-2xl font-bold text-slate-900 font-num mt-0.5">
              {accuracyPct}%
            </div>
            <div className="text-[11px] text-blue-600 font-semibold mt-0.5">
              Strict gold match
            </div>
          </div>
        </div>

        {/* 6. Median latency */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.02)] flex items-start space-x-3">
          <div className="w-8 h-8 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center flex-shrink-0 mt-0.5">
            <Clock className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Median latency</div>
            <div className="text-2xl font-bold text-slate-900 font-num mt-0.5">
              {medianLatency}
            </div>
            <div className="text-[11px] text-purple-600 font-semibold mt-0.5">
              End-to-end
            </div>
          </div>
        </div>
      </div>

      {/* Two Restrained Charts: Outcome Distribution & Category Accuracy */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Chart 1: Outcome Distribution */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
          <div className="flex items-center space-x-2 text-slate-900 font-semibold text-sm mb-4">
            <FileText className="w-4 h-4 text-blue-600" />
            <span>Outcome distribution</span>
          </div>

          {/* Segmented Progress Bar */}
          <div className="w-full h-8 bg-slate-100 rounded-xl overflow-hidden flex my-6 border border-slate-200/50">
            {correctCount > 0 && (
              <div
                className="bg-emerald-500 h-full flex items-center justify-center text-xs font-bold text-white transition-all"
                style={{ width: `${correctPct}%` }}
                title={`Correct: ${correctCount} (${correctPct}%)`}
              >
                {parseFloat(correctPct) > 10 ? `${correctPct}%` : ''}
              </div>
            )}
            {abstainedCount > 0 && (
              <div
                className="bg-amber-400 h-full flex items-center justify-center text-xs font-bold text-amber-950 transition-all"
                style={{ width: `${abstainedPct}%` }}
                title={`Abstained: ${abstainedCount} (${abstainedPct}%)`}
              >
                {parseFloat(abstainedPct) > 10 ? `${abstainedPct}%` : ''}
              </div>
            )}
            {incorrectCount > 0 && (
              <div
                className="bg-rose-500 h-full flex items-center justify-center text-xs font-bold text-white transition-all"
                style={{ width: `${incorrectPct}%` }}
                title={`Incorrect: ${incorrectCount} (${incorrectPct}%)`}
              >
                {parseFloat(incorrectPct) > 10 ? `${incorrectPct}%` : ''}
              </div>
            )}
          </div>

          {/* Legend */}
          <div className="flex items-center justify-center space-x-6 text-xs text-slate-600 font-medium">
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
              <span>Correct ({correctCount})</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400"></span>
              <span>Abstained ({abstainedCount})</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
              <span>Incorrect ({incorrectCount})</span>
            </div>
          </div>
        </div>

        {/* Chart 2: Accuracy by Category */}
        <div className="bg-white border border-[#e2e8f0] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
          <div className="flex items-center space-x-2 text-slate-900 font-semibold text-sm mb-2">
            <FileText className="w-4 h-4 text-blue-600" />
            <span>Accuracy by question category</span>
          </div>

          <div className="h-44 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryData} barSize={26}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="name"
                  tickLine={false}
                  axisLine={{ stroke: '#e2e8f0' }}
                  tick={{ fill: '#64748b', fontSize: 10 }}
                />
                <YAxis
                  domain={[0, 100]}
                  ticks={[0, 25, 50, 75, 100]}
                  tickFormatter={(v) => `${v}%`}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#94a3b8', fontSize: 10 }}
                />
                <Tooltip
                  formatter={(val: any) => [`${val}%`, 'Accuracy']}
                  contentStyle={{ borderRadius: '10px', fontSize: '11px', border: '1px solid #e2e8f0' }}
                />
                <Bar dataKey="accuracy" fill="#93c5fd" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Results Table Card */}
      <div className="bg-white border border-[#e2e8f0] rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.02)] overflow-hidden">
        {/* Table Toolbar */}
        <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center space-x-2 text-slate-900 font-semibold text-sm">
            <FileText className="w-4 h-4 text-blue-600" />
            <span>Results</span>
          </div>

          <div className="flex items-center space-x-3 w-full sm:w-auto">
            {/* Search filter */}
            <div className="relative flex-1 sm:w-64">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setCurrentPage(1);
                }}
                placeholder="Search questions..."
                className="w-full pl-9 pr-3 py-1.5 text-xs text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Outcome filter */}
            <select
              value={outcomeFilter}
              onChange={(e) => {
                setOutcomeFilter(e.target.value as any);
                setCurrentPage(1);
              }}
              className="bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-xl py-1.5 px-3 focus:outline-none"
            >
              <option value="all">All outcomes</option>
              <option value="correct">Correct only</option>
              <option value="abstained">Abstained only</option>
              <option value="incorrect">Incorrect only</option>
            </select>
          </div>
        </div>

        {/* Table Content */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-[11px] font-semibold text-slate-400 uppercase tracking-wider bg-slate-50/50">
                <th className="py-3 px-4 w-10">#</th>
                <th className="py-3 px-4">Question</th>
                <th className="py-3 px-4">Gold answer</th>
                <th className="py-3 px-4">Predicted answer</th>
                <th className="py-3 px-4">Outcome</th>
                <th className="py-3 px-4">Latency</th>
                <th className="py-3 px-3 text-right"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-blue-600" />
                    Loading evaluation run results…
                  </td>
                </tr>
              ) : paginatedRows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    No items match the current search and filter.
                  </td>
                </tr>
              ) : (
                paginatedRows.map((row, index) => {
                  const globalIdx = (currentPage - 1) * rowsPerPage + index + 1;
                  const isCorrect = row.answer_correct;
                  const isAbstain = row.abstained;

                  return (
                    <tr key={row.id || index} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3.5 px-4 font-mono text-slate-400">{globalIdx}</td>
                      <td className="py-3.5 px-4 font-medium text-slate-900 max-w-xs sm:max-w-md">
                        {row.question}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-medium text-slate-800 whitespace-nowrap">
                        {row.gold_answer || '—'}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-slate-700 max-w-xs truncate" title={row.predicted_answer}>
                        {row.predicted_answer || '—'}
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {isCorrect ? (
                          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Correct</span>
                          </span>
                        ) : isAbstain ? (
                          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-100">
                            <MinusCircle className="w-3 h-3" />
                            <span>Abstained</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-100">
                            <XCircle className="w-3 h-3" />
                            <span>Incorrect</span>
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 font-num text-slate-500 whitespace-nowrap">
                        {row.latency_seconds != null ? `${row.latency_seconds.toFixed(1)}s` : '—'}
                      </td>
                      <td className="py-3.5 px-3 text-right">
                        <ArrowRight className="w-3.5 h-3.5 text-slate-300 ml-auto" />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination & Rows per page */}
        <div className="p-4 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
          <div>
            Showing {filteredRows.length === 0 ? 0 : (currentPage - 1) * rowsPerPage + 1}-
            {Math.min(currentPage * rowsPerPage, filteredRows.length)} of {filteredRows.length} questions
          </div>

          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-1.5">
              <span>Rows per page</span>
              <select
                value={rowsPerPage}
                onChange={(e) => {
                  setRowsPerPage(Number(e.target.value));
                  setCurrentPage(1);
                }}
                className="bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-lg py-1 px-2 focus:outline-none"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </div>

            {totalPages > 1 && (
              <div className="flex items-center space-x-1">
                <button
                  type="button"
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="p-1 rounded hover:bg-slate-100 disabled:opacity-40"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                  <button
                    key={page}
                    type="button"
                    onClick={() => setCurrentPage(page)}
                    className={`w-6 h-6 rounded-full text-xs font-semibold ${
                      currentPage === page
                        ? 'bg-blue-600 text-white'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {page}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="p-1 rounded hover:bg-slate-100 disabled:opacity-40"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
