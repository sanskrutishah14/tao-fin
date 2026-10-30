import React from 'react';

interface CompanyLogoProps {
  ticker?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

export const CompanyLogo: React.FC<CompanyLogoProps> = ({
  ticker = '',
  size = 'md',
  className = '',
}) => {
  const t = ticker.toUpperCase();

  const sizeClasses = {
    xs: 'w-4 h-4 text-[9px]',
    sm: 'w-5 h-5 text-[10px]',
    md: 'w-6 h-6 text-xs',
    lg: 'w-8 h-8 text-sm',
    xl: 'w-10 h-10 text-base',
  };

  const currentSizeClass = sizeClasses[size];

  if (t === 'AAPL') {
    return (
      <span className={`inline-flex items-center justify-center ${currentSizeClass} ${className}`}>
        <svg viewBox="0 0 170 170" fill="currentColor" className="w-full h-full text-slate-900">
          <path d="M150.37 130.25c-2.45 5.66-5.35 10.87-8.71 15.66-4.58 6.53-8.33 11.05-11.22 13.56-4.48 4.12-9.28 6.23-14.42 6.35-3.69 0-8.14-1.05-13.32-3.18-5.19-2.12-9.97-3.17-14.34-3.17-4.58 0-9.49 1.05-14.75 3.17-5.26 2.13-9.5 3.24-12.74 3.35-4.35.13-9.16-1.9-14.42-6.08-3.69-3.04-7.67-7.81-11.96-14.34-6.42-9.8-11.36-20.73-14.81-32.8-3.46-12.07-5.19-23.77-5.19-35.1 0-14.15 3.58-26.06 10.74-35.73 7.16-9.67 16.32-14.65 27.49-14.94 4.35 0 9.29 1.12 14.83 3.35 5.54 2.23 9.4 3.46 11.58 3.7 2.5.24 6.75-1.05 12.75-3.87 6-2.82 11.28-4.11 15.84-3.87 13.37.7 23.94 5.3 31.72 13.8-11.63 7.05-17.3 16.7-17.02 28.96.28 9.77 4.09 18.06 11.43 24.87 7.34 6.81 16.14 10.76 26.4 11.85-2.07 6.1-4.7 12.73-7.89 19.89zM119.22 31.81c0-7.72 2.76-14.89 8.28-21.51 5.52-6.62 12.43-10.3 20.73-11.05.21 1.05.32 2.05.32 3 0 7.74-2.83 15-8.5 21.78-5.67 6.78-12.59 10.51-20.76 11.19-.07-.79-.07-2.26-.07-3.41z" />
        </svg>
      </span>
    );
  }

  if (t === 'MSFT') {
    return (
      <span className={`inline-flex items-center justify-center ${currentSizeClass} ${className}`}>
        <svg viewBox="0 0 23 23" className="w-full h-full">
          <rect width="10.8" height="10.8" fill="#F25022" />
          <rect x="12.2" width="10.8" height="10.8" fill="#7FBA00" />
          <rect y="12.2" width="10.8" height="10.8" fill="#00A4EF" />
          <rect x="12.2" y="12.2" width="10.8" height="10.8" fill="#FFB900" />
        </svg>
      </span>
    );
  }

  if (t === 'NVDA') {
    return (
      <span className={`inline-flex items-center justify-center ${currentSizeClass} ${className} bg-[#76b900] rounded p-0.5 text-white font-bold`}>
        <span className="scale-75 tracking-tighter">NV</span>
      </span>
    );
  }

  if (t === 'GOOGL' || t === 'GOOG') {
    return (
      <span className={`inline-flex items-center justify-center ${currentSizeClass} ${className}`}>
        <svg viewBox="0 0 24 24" className="w-full h-full">
          <path
            fill="#4285F4"
            d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"
          />
          <path
            fill="#34A853"
            d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.33 24 12 24z"
          />
          <path
            fill="#FBBC05"
            d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 9.98 0 12s.45 3.82 1.25 5.42l4.03-3.15z"
          />
          <path
            fill="#EA4335"
            d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
          />
        </svg>
      </span>
    );
  }

  if (t === 'AMZN') {
    return (
      <span className={`inline-flex items-center justify-center font-bold text-amber-600 bg-amber-50 rounded-full ${currentSizeClass} ${className}`}>
        a
      </span>
    );
  }

  if (t === 'TSLA') {
    return (
      <span className={`inline-flex items-center justify-center font-bold text-red-600 bg-red-50 rounded-full ${currentSizeClass} ${className}`}>
        T
      </span>
    );
  }

  if (t === 'META') {
    return (
      <span className={`inline-flex items-center justify-center font-semibold text-blue-600 bg-blue-50 rounded-full ${currentSizeClass} ${className}`}>
        ∞
      </span>
    );
  }

  if (t === 'JPM') {
    return (
      <span className={`inline-flex items-center justify-center font-bold text-slate-800 bg-slate-100 rounded ${currentSizeClass} ${className}`}>
        J
      </span>
    );
  }

  if (t === 'V') {
    return (
      <span className={`inline-flex items-center justify-center font-black text-blue-700 italic ${currentSizeClass} ${className}`}>
        V
      </span>
    );
  }

  if (t === 'KO') {
    return (
      <span className={`inline-flex items-center justify-center font-bold text-red-600 bg-red-50 rounded ${currentSizeClass} ${className}`}>
        KO
      </span>
    );
  }

  // Generic fallback with styled letter
  const initial = t.slice(0, 2) || 'C';
  return (
    <span
      className={`inline-flex items-center justify-center font-semibold rounded-md bg-blue-50 text-blue-700 border border-blue-200 ${currentSizeClass} ${className}`}
    >
      {initial}
    </span>
  );
};
