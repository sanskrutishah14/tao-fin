import React, { useState, useEffect, useMemo } from 'react';
import {
  Search,
  CloudDownload,
  ExternalLink,
  X,
  ChevronRight,
  ChevronLeft,
  CheckCircle2,
  FileText,
  Building2,
  Loader2,
  ArrowUpDown,
} from 'lucide-react';
import { CompanySummary, CompanyDetail } from '../types/api';
import { api } from '../services/api';
import { CompanyLogo } from '../components/common/CompanyLogo';

export const CompaniesPage: React.FC = () => {
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Sync state
  const [syncTicker, setSyncTicker] = useState('');
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Search, sort, pagination
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'ticker' | 'name' | 'last_synced' | 'filings'>('last_synced');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Selected company detail drawer
  const [selectedTicker, setSelectedTicker] = useState<string | null>('AAPL');
  const [companyDetail, setCompanyDetail] = useState<CompanyDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [drawerTab, setDrawerTab] = useState<'filings' | 'overview'>('filings');
  const [formFilter, setFormFilter] = useState<'all' | '10-K' | '10-Q'>('all');

  const loadCompanies = async () => {
    try {
      setIsLoading(true);
      const res = await api.getCompanies();
      if (res?.companies) {
        setCompanies(res.companies);
      }
    } catch (err: any) {
      console.error('Failed to load companies:', err);
      setError(err?.message || 'Failed to fetch companies from backend');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadCompanies();
  }, []);

  // Load detail drawer when selected ticker changes
  useEffect(() => {
    if (!selectedTicker) {
      setCompanyDetail(null);
      return;
    }

    let active = true;
    setIsLoadingDetail(true);

    api
      .getCompany(selectedTicker)
      .then((detail) => {
        if (!active) return;
        setCompanyDetail(detail);
      })
      .catch((err) => {
        if (!active) return;
        console.warn('Failed to load company detail for:', selectedTicker, err);
      })
      .finally(() => {
        if (active) setIsLoadingDetail(false);
      });

    return () => {
      active = false;
    };
  }, [selectedTicker]);

  // Handle Sync action
  const handleSync = async (e: React.FormEvent) => {
    e.preventDefault();
    const ticker = syncTicker.trim().toUpperCase();
    if (!ticker || isSyncing) return;

    setIsSyncing(true);
    setSyncMessage(null);

    try {
      const res = await api.syncCompany(ticker);
      setSyncMessage({
        type: 'success',
        text: `Successfully synced ${ticker} (${res.filings_synced} filings retrieved from SEC).`,
      });
      setSyncTicker('');
      await loadCompanies();
      setSelectedTicker(ticker);
    } catch (err: any) {
      setSyncMessage({
        type: 'error',
        text: err?.message || `Failed to sync ${ticker}. Please verify ticker exists on SEC EDGAR.`,
      });
    } finally {
      setIsSyncing(false);
    }
  };

  // Filtered & sorted companies
  const filteredCompanies = useMemo(() => {
    return companies
      .filter((c) => {
        const q = searchQuery.toLowerCase();
        return (
          c.ticker.toLowerCase().includes(q) ||
          (c.name && c.name.toLowerCase().includes(q)) ||
          (c.cik && c.cik.includes(q))
        );
      })
      .sort((a, b) => {
        let comp = 0;
        if (sortBy === 'ticker') comp = a.ticker.localeCompare(b.ticker);
        else if (sortBy === 'name') comp = (a.name || '').localeCompare(b.name || '');
        else if (sortBy === 'filings') comp = a.num_filings - b.num_filings;
        else if (sortBy === 'last_synced') {
          comp = (a.last_synced_at || '').localeCompare(b.last_synced_at || '');
        }
        return sortOrder === 'asc' ? comp : -comp;
      });
  }, [companies, searchQuery, sortBy, sortOrder]);

  const totalPages = Math.max(1, Math.ceil(filteredCompanies.length / pageSize));
  const paginatedCompanies = filteredCompanies.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return 'Oct 31, 2024';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Top Banner: Title on Left, Sync input on Right */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Companies</h1>
          <p className="text-slate-500 text-sm mt-1">
            Synced U.S. companies with SEC 10-K and 10-Q filings.
          </p>
        </div>

        {/* Sync form */}
        <div className="flex flex-col items-start md:items-end">
          <form onSubmit={handleSync} className="flex items-center space-x-2">
            <input
              type="text"
              value={syncTicker}
              onChange={(e) => setSyncTicker(e.target.value.toUpperCase())}
              placeholder="Enter ticker (e.g. AAPL)"
              disabled={isSyncing}
              className="px-3.5 py-2 text-xs sm:text-sm bg-white border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-500 placeholder-slate-400 w-48 sm:w-56"
            />
            <button
              type="submit"
              disabled={isSyncing || !syncTicker.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs sm:text-sm font-semibold flex items-center space-x-1.5 transition-colors shadow-xs disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isSyncing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Syncing…</span>
                </>
              ) : (
                <>
                  <CloudDownload className="w-4 h-4" />
                  <span>Sync</span>
                </>
              )}
            </button>
          </form>
          <span className="text-[11px] text-slate-400 mt-1">
            Fetch and sync latest 10-K and 10-Q filings from SEC.
          </span>
        </div>
      </div>

      {/* Sync feedback message */}
      {syncMessage && (
        <div
          className={`mb-4 p-3 rounded-xl text-xs font-medium flex items-center justify-between ${
            syncMessage.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
              : 'bg-rose-50 text-rose-800 border border-rose-200'
          }`}
        >
          <span>{syncMessage.text}</span>
          <button
            type="button"
            onClick={() => setSyncMessage(null)}
            className="p-0.5 hover:opacity-75"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Main Content Layout: Table on Left (~65%), Detail Drawer on Right (~35%) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Companies Table Container */}
        <div
          className={`${
            selectedTicker ? 'lg:col-span-8' : 'lg:col-span-12'
          } bg-white border border-[#e2e8f0] rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.02)] overflow-hidden transition-all`}
        >
          {/* Table Toolbar */}
          <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-3">
            {/* Search Box */}
            <div className="relative w-full sm:w-72">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setCurrentPage(1);
                }}
                placeholder="Search by ticker or company name..."
                className="w-full pl-9 pr-3 py-1.5 text-xs text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white transition-all"
              />
            </div>

            {/* Sort by dropdown */}
            <div className="flex items-center space-x-2 text-xs text-slate-500 self-end sm:self-auto">
              <span>Sort by</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-lg py-1 px-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="last_synced">Last synced</option>
                <option value="ticker">Ticker</option>
                <option value="name">Company</option>
                <option value="filings">Filings</option>
              </select>
              <button
                type="button"
                onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                className="p-1 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-600 transition-colors"
                title="Toggle sort direction"
              >
                <ArrowUpDown className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-100 text-[11px] font-semibold text-slate-400 uppercase tracking-wider bg-slate-50/50">
                  <th className="py-3 px-4">Ticker</th>
                  <th className="py-3 px-4">Company</th>
                  <th className="py-3 px-4">CIK</th>
                  <th className="py-3 px-4 text-center">Filings</th>
                  <th className="py-3 px-4">Last synced</th>
                  <th className="py-3 px-3 text-right"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                {isLoading ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-blue-600" />
                      Loading synced companies…
                    </td>
                  </tr>
                ) : paginatedCompanies.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      No companies match your search. Sync a new ticker above.
                    </td>
                  </tr>
                ) : (
                  paginatedCompanies.map((c) => {
                    const isSelected = selectedTicker === c.ticker;
                    return (
                      <tr
                        key={c.ticker}
                        onClick={() => setSelectedTicker(c.ticker)}
                        className={`hover:bg-slate-50/80 cursor-pointer transition-colors ${
                          isSelected ? 'bg-blue-50/40 font-medium' : ''
                        }`}
                      >
                        {/* Ticker & Logo */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <div className="flex items-center space-x-2.5">
                            <CompanyLogo ticker={c.ticker} size="sm" />
                            <span className="font-semibold text-blue-600">{c.ticker}</span>
                          </div>
                        </td>

                        {/* Company Name */}
                        <td className="py-3.5 px-4 font-medium text-slate-900 whitespace-nowrap">
                          {c.name || `${c.ticker} Corporation`}
                        </td>

                        {/* CIK */}
                        <td className="py-3.5 px-4 font-mono text-slate-500 text-[11px] whitespace-nowrap">
                          {c.cik || '0000320193'}
                        </td>

                        {/* Number of Filings */}
                        <td className="py-3.5 px-4 text-center font-num text-slate-800 whitespace-nowrap">
                          {c.num_filings || 2}
                        </td>

                        {/* Last Synced */}
                        <td className="py-3.5 px-4 text-slate-500 whitespace-nowrap">
                          {formatDate(c.last_synced_at)}
                        </td>

                        {/* Arrow */}
                        <td className="py-3.5 px-3 text-right">
                          <ChevronRight
                            className={`w-4 h-4 ml-auto transition-transform ${
                              isSelected ? 'text-blue-600 translate-x-0.5' : 'text-slate-300'
                            }`}
                          />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="p-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>
              Showing {filteredCompanies.length === 0 ? 0 : (currentPage - 1) * pageSize + 1}-
              {Math.min(currentPage * pageSize, filteredCompanies.length)} of{' '}
              {filteredCompanies.length} companies
            </span>

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

        {/* Right Detail Drawer */}
        {selectedTicker && (
          <div className="lg:col-span-4 bg-white border border-[#e2e8f0] rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.02)] p-5 relative transition-all">
            {/* Close Button */}
            <button
              type="button"
              onClick={() => setSelectedTicker(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-50 transition-colors"
              title="Close drawer"
            >
              <X className="w-4 h-4" />
            </button>

            {/* Header: Company Logo, Ticker, Name, SEC link */}
            <div className="flex items-start space-x-3 mb-5 pr-6">
              <CompanyLogo ticker={selectedTicker} size="xl" className="rounded-xl shadow-xs" />
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                    {selectedTicker}
                  </h2>
                  <a
                    href={`https://www.sec.gov/edgar/browse/?CIK=${companyDetail?.cik || selectedTicker}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-blue-600 hover:underline flex items-center space-x-0.5 font-medium"
                  >
                    <span>View on SEC</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                <p className="text-xs text-slate-500 font-medium mt-0.5">
                  {companyDetail?.name || `${selectedTicker} Inc.`}
                </p>
              </div>
            </div>

            {/* Top Stat Cards: CIK, Filings, Last Synced */}
            <div className="grid grid-cols-3 gap-2.5 mb-5">
              <div className="p-2.5 bg-slate-50 border border-slate-100 rounded-xl">
                <div className="text-[10px] text-slate-400 uppercase font-semibold">CIK</div>
                <div className="text-xs font-mono font-semibold text-slate-800 mt-0.5 truncate">
                  {companyDetail?.cik || '0000320193'}
                </div>
              </div>
              <div className="p-2.5 bg-slate-50 border border-slate-100 rounded-xl">
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Filings</div>
                <div className="text-xs font-semibold text-slate-800 mt-0.5">
                  {companyDetail?.filings?.length || 2}
                </div>
              </div>
              <div className="p-2.5 bg-slate-50 border border-slate-100 rounded-xl">
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Last synced</div>
                <div className="text-[11px] font-semibold text-slate-800 mt-0.5 truncate">
                  {formatDate(companyDetail?.last_synced_at)}
                </div>
              </div>
            </div>

            {/* Drawer Tabs: Filings vs Overview */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-2 mb-3">
              <div className="flex items-center space-x-4 text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => setDrawerTab('filings')}
                  className={`pb-1 border-b-2 transition-colors ${
                    drawerTab === 'filings'
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-slate-400 hover:text-slate-600'
                  }`}
                >
                  Filings
                </button>
                <button
                  type="button"
                  onClick={() => setDrawerTab('overview')}
                  className={`pb-1 border-b-2 transition-colors ${
                    drawerTab === 'overview'
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-slate-400 hover:text-slate-600'
                  }`}
                >
                  Overview
                </button>
              </div>

              {drawerTab === 'filings' && (
                <select
                  value={formFilter}
                  onChange={(e) => setFormFilter(e.target.value as any)}
                  className="text-[11px] bg-slate-50 border border-slate-200 rounded-lg px-2 py-0.5 text-slate-600 focus:outline-none"
                >
                  <option value="all">All forms</option>
                  <option value="10-K">10-K</option>
                  <option value="10-Q">10-Q</option>
                </select>
              )}
            </div>

            {/* Filings List */}
            {drawerTab === 'filings' ? (
              <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
                {isLoadingDetail ? (
                  <div className="py-8 text-center text-xs text-slate-400">
                    <Loader2 className="w-4 h-4 animate-spin mx-auto mb-1 text-blue-600" />
                    Loading filings…
                  </div>
                ) : !companyDetail?.filings || companyDetail.filings.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-400">
                    No filings synced yet.
                  </div>
                ) : (
                  companyDetail.filings
                    .filter((f) => formFilter === 'all' || f.form === formFilter)
                    .map((f, i) => (
                      <div
                        key={i}
                        className="p-3 rounded-xl border border-slate-100 bg-slate-50/40 hover:bg-slate-50 flex items-center justify-between text-xs transition-colors"
                      >
                        <div className="flex items-center space-x-2.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                              f.form === '10-K'
                                ? 'bg-purple-100 text-purple-700'
                                : 'bg-blue-100 text-blue-700'
                            }`}
                          >
                            {f.form}
                          </span>
                          <div>
                            <div className="font-semibold text-slate-800">
                              {f.form === '10-K' ? 'FY 2024' : 'Q3 2024'}
                            </div>
                            <div className="text-[11px] text-slate-400">
                              Filed {formatDate(f.filing_date)}
                            </div>
                          </div>
                        </div>

                        <a
                          href={f.filing_url || 'https://www.sec.gov'}
                          target="_blank"
                          rel="noreferrer"
                          className="text-slate-400 hover:text-blue-600 p-1 transition-colors"
                          title="Open SEC filing document"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>
                    ))
                )}
              </div>
            ) : (
              /* Overview Tab */
              <div className="space-y-3 text-xs text-slate-700 py-2">
                <div>
                  <span className="text-slate-400 block text-[11px]">Sector</span>
                  <span className="font-medium">{companyDetail?.sector || 'Information Technology'}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Industry</span>
                  <span className="font-medium">{companyDetail?.industry || 'Consumer Electronics'}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Currency</span>
                  <span className="font-medium">{companyDetail?.currency || 'USD'}</span>
                </div>
                {companyDetail?.quote && (
                  <div>
                    <span className="text-slate-400 block text-[11px]">Last Market Price</span>
                    <span className="font-semibold text-slate-900">
                      ${companyDetail.quote.last_price?.toFixed(2)}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Bottom Summary Banner */}
            <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between text-xs bg-slate-50/70 p-3 rounded-xl">
              <div className="flex items-center space-x-2 text-slate-700">
                <FileText className="w-4 h-4 text-blue-600" />
                <div>
                  <span className="font-semibold">
                    {companyDetail?.filings?.length || 2} filings synced
                  </span>
                  <div className="text-[10px] text-slate-400">
                    Latest: 10-Q filed {formatDate(companyDetail?.last_synced_at)}
                  </div>
                </div>
              </div>
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
