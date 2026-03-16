import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, ChevronLeft, ChevronRight } from 'lucide-react';
import client from '../api/client';

function SeverityBadge({ severity }) {
  const colors = {
    critical: 'bg-red-600/20 text-red-400 border-red-600/30',
    high: 'bg-orange-600/20 text-orange-400 border-orange-600/30',
    medium: 'bg-yellow-600/20 text-yellow-400 border-yellow-600/30',
    low: 'bg-green-600/20 text-green-400 border-green-600/30',
  };
  const cls = colors[severity] ?? 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  return <span className={`text-xs font-bold px-2 py-0.5 rounded border uppercase ${cls}`}>{severity}</span>;
}

function StatusBadge({ status }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${status === 'open' ? 'bg-red-900/30 text-red-400 border-red-800' : 'bg-gray-700/30 text-gray-400 border-gray-700'}`}>
      {status}
    </span>
  );
}

export default function Anomalies() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ['anomalies', statusFilter, page],
    queryFn: () =>
      client.get('/anomalies', { params: { status: statusFilter || undefined, page, page_size: pageSize } }).then((r) => r.data),
    refetchInterval: 30_000,
    keepPreviousData: true,
  });

  const totalPages = data ? Math.ceil(data.total / pageSize) : 1;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <AlertTriangle size={24} className="text-amber-500" />
          Anomalies
        </h1>
        <select
          className="bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
        >
          <option value="">All Status</option>
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-left">
                <th className="px-4 py-3 font-medium">Detected</th>
                <th className="px-4 py-3 font-medium">Service</th>
                <th className="px-4 py-3 font-medium">Severity</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Errors</th>
                <th className="px-4 py-3 font-medium">RCA Summary</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={6} className="text-center text-gray-500 py-12">Loading...</td></tr>
              ) : data?.anomalies?.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center text-gray-500 py-12">
                    🎉 No anomalies detected — system looks healthy!
                  </td>
                </tr>
              ) : (
                data?.anomalies?.map((a, i) => (
                  <tr key={a.id ?? i} className="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
                    <td className="px-4 py-3 text-gray-400 whitespace-nowrap font-mono text-xs">
                      {new Date(a.detected_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-blue-400 font-mono text-sm font-medium">{a.service}</td>
                    <td className="px-4 py-3"><SeverityBadge severity={a.severity} /></td>
                    <td className="px-4 py-3"><StatusBadge status={a.status} /></td>
                    <td className="px-4 py-3 text-red-400 font-semibold">{a.error_count}</td>
                    <td className="px-4 py-3 text-gray-300 text-xs max-w-xs truncate">{a.rca}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {data && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800 text-sm text-gray-400">
            <span>{data.total.toLocaleString()} anomalies</span>
            <div className="flex items-center gap-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="p-1.5 rounded hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed">
                <ChevronLeft size={16} />
              </button>
              <span>Page {page} of {totalPages}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="p-1.5 rounded hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed">
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
