import React from 'react';
import { NavLink } from 'react-router-dom';
import { Activity, Search, AlertTriangle, MessageSquare } from 'lucide-react';

const links = [
  { to: '/', label: 'Dashboard', icon: Activity },
  { to: '/logs', label: 'Log Explorer', icon: Search },
  { to: '/anomalies', label: 'Anomalies', icon: AlertTriangle },
  { to: '/query', label: 'NL Query', icon: MessageSquare },
];

export default function Navbar() {
  return (
    <nav className="bg-gray-900 border-b border-gray-800 sticky top-0 z-50">
      <div className="container mx-auto px-4 flex items-center justify-between h-16">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🔍</span>
          <span className="font-bold text-lg text-white">AI Log Analyzer</span>
        </div>
        <div className="flex items-center gap-1">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
}
