import React from 'react';
import {
  Home,
  Building2,
  TrendingUp,
  CheckSquare,
  Info,
  Sun,
  Moon,
} from 'lucide-react';

export type NavigationTab = 'ask' | 'companies' | 'market' | 'evaluation' | 'about';

interface NavbarProps {
  currentTab: NavigationTab;
  onTabChange: (tab: NavigationTab) => void;
  darkMode: boolean;
  onToggleDarkMode: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onTabChange,
  darkMode,
  onToggleDarkMode,
}) => {
  const navItems = [
    { id: 'ask' as const, label: 'Ask', icon: Home },
    { id: 'companies' as const, label: 'Companies', icon: Building2 },
    { id: 'market' as const, label: 'Market', icon: TrendingUp },
    { id: 'evaluation' as const, label: 'Evaluation', icon: CheckSquare },
    { id: 'about' as const, label: 'About', icon: Info },
  ];

  return (
    <header className="sticky top-0 z-40 bg-white dark:bg-[#111827] border-b border-[#e2e8f0] dark:border-[#1f2937] shadow-[0_1px_2px_rgba(0,0,0,0.03)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.2)] transition-colors duration-200">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <div className="flex items-center space-x-8">
          <button
            onClick={() => onTabChange('ask')}
            className="flex items-center space-x-2.5 focus:outline-none group text-left"
          >
            {/* TAO-Fin 3 rounded bars logo */}
            <div className="flex items-end space-x-1 h-5">
              <span className="w-1.5 h-3.5 bg-blue-600 rounded-full"></span>
              <span className="w-1.5 h-5 bg-blue-600 rounded-full"></span>
              <span className="w-1.5 h-2.5 bg-blue-600 rounded-full"></span>
            </div>
            <span className="text-xl font-bold tracking-tight text-slate-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
              TAO-Fin
            </span>
          </button>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onTabChange(item.id)}
                  className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400'
                      : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600 dark:text-blue-400' : 'text-slate-500 dark:text-slate-400'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Right Controls: Theme Toggle & Avatar */}
        <div className="flex items-center space-x-3">
          {/* Light / Dark Mode Toggle Pill */}
          <button
            type="button"
            onClick={onToggleDarkMode}
            title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            className="relative flex items-center justify-between w-14 h-7 p-1 bg-slate-100 dark:bg-slate-800 rounded-full border border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 transition-colors focus:outline-none"
          >
            <Sun className={`w-3.5 h-3.5 ml-0.5 ${!darkMode ? 'text-amber-500' : 'text-slate-400'}`} />
            <Moon className={`w-3.5 h-3.5 mr-0.5 ${darkMode ? 'text-blue-300' : 'text-slate-400'}`} />
            <div
              className={`absolute top-0.5 bottom-0.5 w-6 h-6 rounded-full flex items-center justify-center transition-transform duration-200 shadow-xs ${
                darkMode ? 'translate-x-7 bg-blue-600 text-white' : 'translate-x-0 bg-white text-slate-800'
              }`}
            >
              {darkMode ? <Moon className="w-3 h-3 text-white" /> : <Sun className="w-3 h-3 text-amber-500" />}
            </div>
          </button>

          {/* User Initial Avatar "K" */}
          <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 font-semibold text-sm flex items-center justify-center border border-blue-200 dark:border-blue-800">
            K
          </div>
        </div>
      </div>

      {/* Mobile nav bar */}
      <div className="md:hidden flex items-center justify-around border-t border-slate-100 dark:border-slate-800 py-1 bg-white dark:bg-[#111827] px-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`flex flex-col items-center py-1 px-2 text-xs font-medium rounded ${
                isActive ? 'text-blue-600 dark:text-blue-400' : 'text-slate-500 dark:text-slate-400'
              }`}
            >
              <Icon className="w-4 h-4 mb-0.5" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </header>
  );
};
