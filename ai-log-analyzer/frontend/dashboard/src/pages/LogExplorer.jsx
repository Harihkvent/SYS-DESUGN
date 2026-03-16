import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, ChevronLeft, ChevronRight } from 'lucide-react';
import client from '../api/client';

const LEVELS = ['', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'];

function LevelBadge({ level }) {
  const colors = {
    ERROR: 'bg-red-500/20 text-red-400 border-red-500/30',
    CRITICAL: 'bg-red-700/20 text-red-300 border-red-700/30',
    WARN: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    WARNING: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    INFO: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    DEBUG: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  };
  const cls = colors[level] ?? 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  return <span className={`text-xs font-bold px-2 py-0.5 rounded border ${cls}`}>{level}</span>;
}

export default function LogExplorer() {
  const [service, setService] = useState('');
  const [level, setLevel] = useState('');
  const [q, setQ] = useState('');
  const [search, setSearch] = useState({ service: '', level: '', q: '' });
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const { data, isLoading } = useQuery({
    queryKey: ['logs', search, page],
    queryFn: () =>
      client
        .get('/logs', { params: { service: search.service || undefined, level: search.level || undefined, q: search.q || undefined, page, page_size: pageSize } })
        .then((r) => r.data),
    keepPreviousData: true,
  });

  const totalPages = data ? Math.ceil(data.total / pageSize) : 1;

  const handleSearch = (e) => {
    e.preventDefault();
    setSearch({ service, level, q });
    setPage(1);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-white">Log Explorer</h1>

      <form onSubmit={handleSearch} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-wrap gap-3">
        <input
          className="flex-1 min-w-48 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
          placeholder="Search message..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <input
          className="w-40 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
          placeholder="Service name"
          value={service}
          onChange={(e) => setService(e.target.value)}
        />
        <select
          className="w-36 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
          value={level}
          onChange={(e) => setLevel(e.target.value)}
        >
          {LEVELS.map((l) => (
            <option key={l} value={l}>{l || 'All Levels'}</option>
          ))}
        </select>
        <button
          type="submit"
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <Search size={16} /> Search
        </button>
      </form>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-left">
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Level</th>
                <th className="px-4 py-3 font-medium">Service</th>
                <th className="px-4 py-3 font-medium">Host</th>
                <th className="px-4 py-3 font-medium w-1/2">Message</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={5} className="text-center text-gray-500 py-12">Loading...</td></tr>
              ) : data?.logs?.length === 0 ? (
                <tr><td colSpan={5} className="text-center text-gray-500 py-12">No logs found</td></tr>
              ) : (
                data?.logs?.map((log, i) => (
                  <tr key={log.id ?? i} className="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
                    <td className="px-4 py-2 text-gray-400 whitespace-nowrap font-mono text-xs">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-2"><LevelBadge level={log.level} /></td>
                    <td className="px-4 py-2 text-blue-400 font-mono text-xs">{log.service}</td>
                    <td className="px-4 py-2 text-gray-400 font-mono text-xs">{log.host}</td>
                    <td className="px-4 py-2 text-gray-200 font-mono text-xs truncate max-w-md">{log.message}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {data && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800 text-sm text-gray-400">
            <span>{data.total.toLocaleString()} results</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronLeft size={16} />
              </button>
              <span>Page {page} of {totalPages}</span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
