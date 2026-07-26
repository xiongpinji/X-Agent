/* Analytics dashboard frontend component. */

import React, { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface RealtimeStats {
  timestamp: string;
  active_users: number;
  active_sessions: number;
  api_calls_per_minute: number;
  tokens_per_minute: number;
  error_rate: number;
  avg_response_time_ms: number;
  current_throughput: number;
}

interface CostAnalysis {
  total_cost_usd: number;
  cost_by_model: Record<string, number>;
  cost_by_feature: Record<string, number>;
  cost_by_user: Record<string, number>;
  cost_trend: number;
}

interface PerformanceAnalysis {
  avg_response_time_ms: number;
  p95_response_time_ms: number;
  p99_response_time_ms: number;
  error_rate: number;
  success_rate: number;
  throughput_rps: number;
  slow_endpoints: Array<{ endpoint: string; avg_time_ms: number }>;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

export const AnalyticsDashboard: React.FC = () => {
  const [realtimeStats, setRealtimeStats] = useState<RealtimeStats | null>(null);
  const [costAnalysis, setCostAnalysis] = useState<CostAnalysis | null>(null);
  const [performanceAnalysis, setPerformanceAnalysis] = useState<PerformanceAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [realtimeRes, costRes, perfRes] = await Promise.all([
          fetch('/api/v1/analytics/realtime'),
          fetch('/api/v1/analytics/costs'),
          fetch('/api/v1/analytics/performance'),
        ]);

        if (!realtimeRes.ok || !costRes.ok || !perfRes.ok) {
          throw new Error('Failed to fetch analytics data');
        }

        const [realtimeData, costData, perfData] = await Promise.all([
          realtimeRes.json(),
          costRes.json(),
          perfRes.json(),
        ]);

        setRealtimeStats(realtimeData);
        setCostAnalysis(costData);
        setPerformanceAnalysis(perfData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div className="p-8">Loading analytics...</div>;
  }

  if (error) {
    return <div className="p-8 text-red-600">Error: {error}</div>;
  }

  return (
    <div className="p-8 bg-gray-50">
      <h1 className="text-3xl font-bold mb-8">Analytics Dashboard</h1>

      {/* Real-time Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatCard
          title="Active Users"
          value={realtimeStats?.active_users || 0}
          unit="users"
        />
        <StatCard
          title="API Calls/min"
          value={realtimeStats?.api_calls_per_minute || 0}
          unit="calls"
        />
        <StatCard
          title="Error Rate"
          value={(realtimeStats?.error_rate || 0) * 100}
          unit="%"
        />
        <StatCard
          title="Avg Response Time"
          value={realtimeStats?.avg_response_time_ms || 0}
          unit="ms"
        />
      </div>

      {/* Cost Analysis */}
      {costAnalysis && (
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-xl font-bold mb-4">Cost Analysis</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <p className="text-gray-600 mb-2">Total Cost</p>
              <p className="text-3xl font-bold">${costAnalysis.total_cost_usd.toFixed(2)}</p>
              <p className={`text-sm ${costAnalysis.cost_trend > 0 ? 'text-red-600' : 'text-green-600'}`}>
                {costAnalysis.cost_trend > 0 ? '+' : ''}{costAnalysis.cost_trend.toFixed(1)}% from previous period
              </p>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={Object.entries(costAnalysis.cost_by_model).map(([name, value]) => ({
                    name,
                    value,
                  }))}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: $${value.toFixed(2)}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {Object.entries(costAnalysis.cost_by_model).map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => `$${Number(value).toFixed(2)}`} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Performance Analysis */}
      {performanceAnalysis && (
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-xl font-bold mb-4">Performance Analysis</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <StatCard
              title="Avg Response Time"
              value={performanceAnalysis.avg_response_time_ms}
              unit="ms"
            />
            <StatCard
              title="P95 Response Time"
              value={performanceAnalysis.p95_response_time_ms}
              unit="ms"
            />
            <StatCard
              title="Success Rate"
              value={performanceAnalysis.success_rate * 100}
              unit="%"
            />
          </div>

          {/* Slow Endpoints */}
          <div className="mt-6">
            <h3 className="text-lg font-semibold mb-4">Slowest Endpoints</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={performanceAnalysis.slow_endpoints}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="endpoint" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="avg_time_ms" fill="#8884d8" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
};

interface StatCardProps {
  title: string;
  value: number;
  unit: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, unit }) => (
  <div className="bg-white rounded-lg shadow p-6">
    <p className="text-gray-600 text-sm mb-2">{title}</p>
    <p className="text-2xl font-bold">
      {value.toLocaleString(undefined, { maximumFractionDigits: 2 })} {unit}
    </p>
  </div>
);

export default AnalyticsDashboard;
