import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, AlertTriangle, TrendingUp, Zap } from 'lucide-react';
import client from '../api/client';

function StatCard({ title, value, icon: Icon, color, subtitle }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex items-start gap-4">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon size={22} className="text-white" />
      </div>
      <div>
        <p className="text-gray-400 text-sm">{title}</p>
        <p className="text-3xl font-bold text-white mt-1">{value ?? '—'}</p>
        {subtitle && <p className="text-gray-500 text-xs mt-1">{subtitle}</p>}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['stats'],
    queryFn: () => client.get('/stats').then((r) => r.data),
    refetchInterval: 30_000,
  });

  const chartData = data?.time_series?.map((d) => ({
    time: new Date(d.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    count: d.count,
  })) ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Overview Dashboard</h1>

      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg p-4 text-red-400">
          Failed to load stats. Is the API service running?
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard
          title="Total Logs (Last Hour)"
          value={isLoading ? '...' : (data?.total_logs_last_hour ?? 0).toLocaleString()}
          icon={Activity}
          color="bg-blue-600"
          subtitle="Rolling 60-minute window"
        />
        <StatCard
          title="Open Anomalies"
          value={isLoading ? '...' : data?.open_anomalies ?? 0}
          icon={AlertTriangle}
          color="bg-amber-600"
          subtitle="Requires attention"
        />
        <StatCard
          title="Error Rate"
          value={isLoading ? '...' : `${data?.error_rate_percent ?? 0}%`}
          icon={TrendingUp}
          color={data?.error_rate_percent > 10 ? 'bg-red-600' : 'bg-green-600'}
          subtitle="ERROR + CRITICAL / total"
        />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Zap size={18} className="text-blue-400" />
          Log Volume (Last Hour)
        </h2>
        {chartData.length === 0 && !isLoading ? (
          <p className="text-gray-500 text-center py-12">No data yet. Send some logs to the ingestion service.</p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="time" stroke="#6b7280" tick={{ fontSize: 12 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#e5e7eb' }}
              />
              <Line type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Level Breakdown</h2>
        <div className="flex flex-wrap gap-3">
          {Object.entries(data?.level_counts ?? {}).map(([level, count]) => (
            <div key={level} className="flex items-center gap-2 bg-gray-800 rounded-lg px-4 py-2">
              <LevelBadge level={level} />
              <span className="text-white font-semibold">{count}</span>
            </div>
          ))}
          {!data?.level_counts || Object.keys(data.level_counts).length === 0 ? (
            <p className="text-gray-500 text-sm">No data</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function LevelBadge({ level }) {
  const colors = {
    ERROR: 'bg-red-500/20 text-red-400',
    CRITICAL: 'bg-red-700/20 text-red-300',
    WARN: 'bg-yellow-500/20 text-yellow-400',
    WARNING: 'bg-yellow-500/20 text-yellow-400',
    INFO: 'bg-blue-500/20 text-blue-400',
    DEBUG: 'bg-gray-500/20 text-gray-400',
  };
  const cls = colors[level] ?? 'bg-gray-500/20 text-gray-400';
  return <span className={`text-xs font-bold px-2 py-0.5 rounded ${cls}`}>{level}</span>;
}
