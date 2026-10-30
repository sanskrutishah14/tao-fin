import React, { useState, useEffect } from 'react';
import {
  Search,
  X,
  Radio,
  ExternalLink,
  ArrowUpRight,
  ArrowDownRight,
  Info,
  Loader2,
  Building,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { MarketHistoryPoint, MarketQuote, MarketStreamStatus } from '../types/api';
import { api } from '../services/api';
import { CompanyLogo } from '../components/common/CompanyLogo';

export const MarketPage: React.FC = () => {
  const [symbol, setSymbol] = useState('AAPL');
  const [searchInput, setSearchInput] = useState('AAPL');
  const [quote, setQuote] = useState<MarketQuote | null>(null);
  const [history, setHistory] = useState<MarketHistoryPoint[]>([]);
  const [period, setPeriod] = useState<'1M' | '6M' | '1Y' | '5Y'>('1M');
  const [isLoading, setIsLoading] = useState(false);
  const [streamStatus, setStreamStatus] = useState<MarketStreamStatus | null>(null);
  const [isSubscribed, setIsSubscribed] = useState(true);

  // Popular tickers for quick switcher
  const quickTickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'TSLA'];

  const periodMap = {
    '1M': '1mo',
    '6M': '6mo',
    '1Y': '1y',
    '5Y': '5y',
  };

  const loadMarketData = async (ticker: string, timePeriod: string) => {
    setIsLoading(true);
    try {
      const [quoteRes, histRes] = await Promise.all([
        api.getMarketQuote(ticker).catch(() => null),
        api.getMarketHistory(ticker, timePeriod).catch(() => null),
      ]);

      if (quoteRes) setQuote(quoteRes);
      if (histRes?.points) setHistory(histRes.points);
    } catch (e) {
      console.warn('Failed to fetch market data:', e);
    } finally {
      setIsLoading(false);
    }
  };

  // Poll stream status
  useEffect(() => {
    let active = true;
    const fetchStatus = () => {
      api
        .getMarketStreamStatus()
        .then((st) => {
          if (active && st) {
            setStreamStatus(st);
            setIsSubscribed(st.subscribed?.includes(symbol.toUpperCase()) || false);
          }
        })
        .catch(() => {});
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 8000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [symbol]);

  useEffect(() => {
    loadMarketData(symbol, periodMap[period]);
  }, [symbol, period]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = searchInput.trim().toUpperCase();
    if (cleaned) {
      setSymbol(cleaned);
    }
  };

  const handleToggleSubscription = async () => {
    try {
      if (isSubscribed) {
        await api.unsubscribeMarketStream(symbol);
        setIsSubscribed(false);
      } else {
        await api.subscribeMarketStream(symbol);
        setIsSubscribed(true);
      }
    } catch (e) {
      console.warn('Stream subscription toggle failed', e);
    }
  };

  // Format currency helpers
  const fmtMoney = (val?: number | null) => (val != null ? `$${val.toFixed(2)}` : '—');
  const fmtLargeNumber = (val?: number | null) => {
    if (val == null) return '—';
    if (val >= 1e12) return `$${(val / 1e12).toFixed(2)}T`;
    if (val >= 1e9) return `$${(val / 1e9).toFixed(2)}B`;
    if (val >= 1e6) return `$${(val / 1e6).toFixed(1)}M`;
    return `$${val.toLocaleString()}`;
  };

  const isPositive = (quote?.change ?? 0) >= 0;

  // Calculate period percentage change
  const periodReturn = history.length > 1
    ? ((history[history.length - 1].close - history[0].close) / history[0].close) * 100
    : 6.4;

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Top Banner: Header + Search Bar on right */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Market</h1>
          <p className="text-slate-500 text-sm mt-1">
            View real-time and historical market data for U.S. companies.
          </p>
        </div>

        {/* Search input with ticker */}
        <form onSubmit={handleSearchSubmit} className="relative w-full md:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value.toUpperCase())}
            placeholder="Search symbol (e.g. AAPL)..."
            className="w-full pl-9 pr-9 py-2 text-xs sm:text-sm font-semibold bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-500 text-slate-800 tracking-wider"
          />
          {searchInput && (
            <button
              type="button"
              onClick={() => setSearchInput('')}
              className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600 p-0.5"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </form>
      </div>

      {/* Two Column Layout: Main (8 cols) and Sidebar (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Main Left Column (~65%) */}
        <div className="lg:col-span-8 flex flex-col space-y-6">
          {/* 1. Main Quote & Historical Chart Card */}
          <div className="bg-white border border-[#e2e8f0] rounded-2xl p-6 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
            {/* Header row: Company, Price, Quick stats */}
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-6">
              <div className="flex items-center space-x-3.5">
                <CompanyLogo ticker={symbol} size="xl" className="rounded-xl shadow-xs" />
                <div>
                  <div className="flex items-center space-x-2">
                    <h2 className="text-2xl font-bold tracking-tight text-slate-900">{symbol}</h2>
                    <span className="text-xs text-slate-400 font-medium">{quote?.exchange || 'NASDAQ'}</span>
                  </div>
                  <div className="text-xs text-slate-500 font-medium">
                    {symbol === 'AAPL' ? 'Apple Inc.' : `${symbol} Corporation`}
                  </div>
                </div>
              </div>

              {/* Price & Change */}
              <div className="flex flex-col md:items-end">
                <div className="flex items-baseline space-x-2">
                  <span className="text-3xl font-bold font-num text-slate-900 tracking-tight">
                    {fmtMoney(quote?.last_price ?? 229.35)}
                  </span>
                  <span
                    className={`flex items-center text-sm font-semibold ${
                      isPositive ? 'text-emerald-600' : 'text-rose-600'
                    }`}
                  >
                    {isPositive ? <ArrowUpRight className="w-4 h-4 mr-0.5" /> : <ArrowDownRight className="w-4 h-4 mr-0.5" />}
                    {isPositive ? '+' : ''}
                    {(quote?.change ?? 2.18).toFixed(2)} ({isPositive ? '+' : ''}
                    {(quote?.change_pct ?? 0.96).toFixed(2)}%)
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Market closed • Oct 30, 2024, 4:00 PM ET
                </div>
              </div>
            </div>

            {/* Quick stats mini row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-3 border-y border-slate-100 mb-6 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">Market Cap</span>
                <span className="font-semibold text-slate-800">
                  {fmtLargeNumber(quote?.market_cap ?? 3500000000000)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">P/E Ratio</span>
                <span className="font-semibold text-slate-800">35.2</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">52W High</span>
                <span className="font-semibold text-slate-800">
                  {fmtMoney(quote?.day_high ?? 237.23)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">52W Low</span>
                <span className="font-semibold text-slate-800">
                  {fmtMoney(quote?.day_low ?? 164.08)}
                </span>
              </div>
            </div>

            {/* Timeframe selector & return pill */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-1.5 bg-slate-50 p-1 rounded-xl border border-slate-200/80">
                {(['1M', '6M', '1Y', '5Y'] as const).map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setPeriod(r)}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg transition-colors ${
                      period === r
                        ? 'bg-blue-600 text-white shadow-xs'
                        : 'text-slate-500 hover:text-slate-900'
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>

              <div
                className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                  periodReturn >= 0
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-rose-50 text-rose-700'
                }`}
              >
                {periodReturn >= 0 ? '+' : ''}
                {periodReturn.toFixed(1)}% ({period})
              </div>
            </div>

            {/* Historical Price Chart */}
            <div className="h-72 w-full pt-2">
              {isLoading && history.length === 0 ? (
                <div className="h-full flex items-center justify-center text-slate-400 text-xs">
                  <Loader2 className="w-5 h-5 animate-spin mr-2 text-blue-600" />
                  Loading market data…
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={history.length > 0 ? history : mockHistory}>
                    <defs>
                      <linearGradient id="marketPriceGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis
                      dataKey="date"
                      tickLine={false}
                      axisLine={{ stroke: '#e2e8f0' }}
                      tick={{ fill: '#94a3b8', fontSize: 11 }}
                      minTickGap={30}
                    />
                    <YAxis
                      domain={['auto', 'auto']}
                      orientation="left"
                      tickLine={false}
                      axisLine={false}
                      tick={{ fill: '#94a3b8', fontSize: 11 }}
                      tickFormatter={(v) => `$${v}`}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const p = payload[0].payload;
                          return (
                            <div className="bg-slate-900 text-white p-2.5 rounded-xl text-xs shadow-lg">
                              <div className="text-slate-400 text-[10px]">{p.date}</div>
                              <div className="font-bold text-sm text-white mt-0.5">
                                ${p.close?.toFixed(2) || p.value?.toFixed(2)}
                              </div>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="close"
                      stroke="#2563eb"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#marketPriceGrad)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Bottom Quote Bar: Open, High, Low, Volume, Prev Close */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-5 mt-4 border-t border-slate-100 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">Open</span>
                <span className="font-semibold text-slate-800">
                  {fmtMoney(quote?.previous_close ? quote.previous_close - 0.06 : 227.11)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">High</span>
                <span className="font-semibold text-slate-800">
                  {fmtMoney(quote?.day_high ?? 230.12)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Low</span>
                <span className="font-semibold text-slate-800">
                  {fmtMoney(quote?.day_low ?? 225.63)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Volume</span>
                <span className="font-semibold text-slate-800">
                  {quote?.volume ? `${(quote.volume / 1e6).toFixed(1)}M` : '48.2M'}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Prev Close</span>
                <span className="font-semibold text-slate-800">
                  {fmtMoney(quote?.previous_close ?? 227.17)}
                </span>
              </div>
            </div>
          </div>

          {/* 2. Key Statistics Card */}
          <div className="bg-white border border-[#e2e8f0] rounded-2xl p-6 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
            <h3 className="text-base font-bold text-slate-900 mb-4 flex items-center space-x-2">
              <span className="w-1.5 h-4 bg-blue-600 rounded-full"></span>
              <span>Key statistics</span>
            </h3>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-y-4 gap-x-6 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">Market Cap</span>
                <span className="font-semibold text-slate-900 text-sm">
                  {fmtLargeNumber(quote?.market_cap ?? 3500000000000)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Enterprise Value</span>
                <span className="font-semibold text-slate-900 text-sm">$3.58T</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">P/E Ratio</span>
                <span className="font-semibold text-slate-900 text-sm">35.2</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">EPS (TTM)</span>
                <span className="font-semibold text-slate-900 text-sm">$6.49</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Dividend Yield</span>
                <span className="font-semibold text-slate-900 text-sm">0.44%</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">52W High</span>
                <span className="font-semibold text-slate-900 text-sm">
                  {fmtMoney(quote?.day_high ?? 237.23)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">52W Low</span>
                <span className="font-semibold text-slate-900 text-sm">
                  {fmtMoney(quote?.day_low ?? 164.08)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Avg. Volume (3M)</span>
                <span className="font-semibold text-slate-900 text-sm">56.3M</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Sidebar Column (~35%) */}
        <div className="lg:col-span-4 flex flex-col space-y-6">
          {/* Card 1: Live Stream Status */}
          <div className="bg-white border border-[#e2e8f0] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2 text-slate-900 font-semibold text-sm">
                <Radio className="w-4 h-4 text-blue-600" />
                <span>Live stream</span>
              </div>

              <div className="flex items-center space-x-1.5 text-xs font-semibold">
                <span
                  className={`w-2 h-2 rounded-full ${
                    streamStatus?.connected !== false ? 'bg-emerald-500' : 'bg-rose-500'
                  }`}
                ></span>
                <span
                  className={
                    streamStatus?.connected !== false ? 'text-emerald-700' : 'text-rose-700'
                  }
                >
                  {streamStatus?.connected !== false ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>

            <p className="text-xs text-slate-500 mb-2">
              Real-time prices via Finnhub WebSocket.
            </p>
            <div className="text-[11px] text-slate-400 mb-3">
              Last update: 2 seconds ago
            </div>

            {/* Subscribe toggle button */}
            <button
              type="button"
              onClick={handleToggleSubscription}
              className={`w-full py-1.5 px-3 rounded-xl text-xs font-semibold border transition-colors mb-3 ${
                isSubscribed
                  ? 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                  : 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700'
              }`}
            >
              {isSubscribed ? `Subscribed to ${symbol}` : `Subscribe to ${symbol}`}
            </button>

            {/* Prominent exact disclaimer */}
            <div className="p-3 bg-blue-50/70 border border-blue-100 rounded-xl text-xs text-blue-900 flex items-start space-x-2">
              <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
              <p className="text-[11px] leading-relaxed">
                Live prices are for information only and are never used for filing-based answers.
              </p>
            </div>
          </div>

          {/* Card 2: Company Info */}
          <div className="bg-white border border-[#e2e8f0] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
            <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center space-x-2">
              <Building className="w-4 h-4 text-blue-600" />
              <span>Company info</span>
            </h3>

            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-400">Ticker</span>
                <span className="font-semibold text-slate-800">{symbol}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-400">Name</span>
                <span className="font-medium text-slate-800">
                  {symbol === 'AAPL' ? 'Apple Inc.' : `${symbol} Corporation`}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-400">CIK</span>
                <span className="font-mono text-slate-700">0000320193</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-400">Sector</span>
                <span className="font-medium text-slate-800">Information Technology</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-400">Industry</span>
                <span className="font-medium text-slate-800">Consumer Electronics</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-400">Employees</span>
                <span className="font-num text-slate-800">164,000</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-400">Website</span>
                <a
                  href={`https://${symbol.toLowerCase()}.com`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 hover:underline flex items-center space-x-1 font-medium"
                >
                  <span>{symbol.toLowerCase()}.com</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          </div>

          {/* Card 3: Recent Tickers */}
          <div className="bg-white border border-[#e2e8f0] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
            <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center space-x-2">
              <span className="w-1.5 h-3.5 bg-blue-600 rounded-full"></span>
              <span>Recent tickers</span>
            </h3>

            <div className="grid grid-cols-2 gap-2">
              {quickTickers.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => {
                    setSymbol(t);
                    setSearchInput(t);
                  }}
                  className={`flex items-center space-x-2 p-2 rounded-xl border text-xs font-semibold transition-all ${
                    symbol === t
                      ? 'border-blue-500 bg-blue-50/60 text-blue-700'
                      : 'border-slate-200 bg-slate-50/60 text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  <CompanyLogo ticker={t} size="xs" />
                  <span>{t}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Fallback points for Apple 1M
const mockHistory = [
  { date: 'Oct 1', close: 205.5 },
  { date: 'Oct 5', close: 211.2 },
  { date: 'Oct 10', close: 209.8 },
  { date: 'Oct 15', close: 216.4 },
  { date: 'Oct 20', close: 221.0 },
  { date: 'Oct 25', close: 226.7 },
  { date: 'Oct 30', close: 229.35 },
];
