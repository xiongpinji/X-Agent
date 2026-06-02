import React from 'react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { FeedbackStats, FeedbackTrend } from '@/services/feedback'
import clsx from 'clsx'

interface FeedbackVisualizationProps {
  stats: FeedbackStats | null
  trends: FeedbackTrend[] | null
  isLoading: boolean
  theme: 'light' | 'dark'
}

const COLORS = {
  bug: '#ef4444',
  feature: '#3b82f6',
  improvement: '#10b981',
  other: '#8b5cf6',
  positive: '#10b981',
  neutral: '#f59e0b',
  negative: '#ef4444',
  critical: '#dc2626',
  high: '#f97316',
  medium: '#eab308',
  low: '#3b82f6',
}

export const FeedbackVisualization: React.FC<FeedbackVisualizationProps> = ({
  stats,
  trends,
  isLoading,
  theme,
}) => {
  if (isLoading) {
    return (
      <div className={clsx(
        'p-8 text-center rounded-lg',
        theme === 'dark' ? 'bg-slate-800' : 'bg-slate-100'
      )}>
        <p className={theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}>
          Loading visualizations...
        </p>
      </div>
    )
  }

  if (!stats || !trends) {
    return (
      <div className={clsx(
        'p-8 text-center rounded-lg',
        theme === 'dark' ? 'bg-slate-800' : 'bg-slate-100'
      )}>
        <p className={theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}>
          No data available
        </p>
      </div>
    )
  }

  // Prepare data for charts
  const typeData = Object.entries(stats.byType).map(([name, value]) => ({
    name,
    value,
  }))

  const statusData = Object.entries(stats.byStatus).map(([name, value]) => ({
    name,
    value,
  }))

  const sentimentData = Object.entries(stats.bySentiment).map(([name, value]) => ({
    name,
    value,
  }))

  const priorityData = Object.entries(stats.byPriority).map(([name, value]) => ({
    name,
    value,
  }))

  const trendData = trends.map((trend) => ({
    date: new Date(trend.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    count: trend.count,
  }))

  const chartConfig = {
    backgroundColor: theme === 'dark' ? '#1e293b' : '#ffffff',
    textColor: theme === 'dark' ? '#cbd5e1' : '#334155',
    gridColor: theme === 'dark' ? '#475569' : '#e2e8f0',
  }

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total Feedbacks"
          value={stats.total}
          theme={theme}
        />
        <MetricCard
          label="Resolution Rate"
          value={`${(stats.resolutionRate * 100).toFixed(1)}%`}
          theme={theme}
        />
        <MetricCard
          label="Avg Resolution Time"
          value={`${Math.round(stats.avgResolutionTime)} days`}
          theme={theme}
        />
        <MetricCard
          label="Open Issues"
          value={stats.byStatus['open'] || 0}
          theme={theme}
        />
      </div>

      {/* Trends Chart */}
      <div className={clsx(
        'p-6 rounded-lg border',
        theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'
      )}>
        <h3 className={clsx(
          'text-lg font-semibold mb-4',
          theme === 'dark' ? 'text-white' : 'text-slate-900'
        )}>
          Feedback Trends
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={trendData}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={chartConfig.gridColor}
            />
            <XAxis
              dataKey="date"
              stroke={chartConfig.textColor}
              style={{ fontSize: '12px' }}
            />
            <YAxis
              stroke={chartConfig.textColor}
              style={{ fontSize: '12px' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: chartConfig.backgroundColor,
                border: `1px solid ${chartConfig.gridColor}`,
                color: chartConfig.textColor,
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="count"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ fill: '#3b82f6', r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Type and Status Distribution */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Type Distribution */}
        <div className={clsx(
          'p-6 rounded-lg border',
          theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'
        )}>
          <h3 className={clsx(
            'text-lg font-semibold mb-4',
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          )}>
            By Type
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={typeData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value }) => `${name}: ${value}`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {typeData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[entry.name as keyof typeof COLORS] || '#8884d8'}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: chartConfig.backgroundColor,
                  border: `1px solid ${chartConfig.gridColor}`,
                  color: chartConfig.textColor,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Status Distribution */}
        <div className={clsx(
          'p-6 rounded-lg border',
          theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'
        )}>
          <h3 className={clsx(
            'text-lg font-semibold mb-4',
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          )}>
            By Status
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={statusData}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={chartConfig.gridColor}
              />
              <XAxis
                dataKey="name"
                stroke={chartConfig.textColor}
                style={{ fontSize: '12px' }}
              />
              <YAxis
                stroke={chartConfig.textColor}
                style={{ fontSize: '12px' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: chartConfig.backgroundColor,
                  border: `1px solid ${chartConfig.gridColor}`,
                  color: chartConfig.textColor,
                }}
              />
              <Bar dataKey="value" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Sentiment and Priority Distribution */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Sentiment Distribution */}
        <div className={clsx(
          'p-6 rounded-lg border',
          theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'
        )}>
          <h3 className={clsx(
            'text-lg font-semibold mb-4',
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          )}>
            By Sentiment
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={sentimentData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value }) => `${name}: ${value}`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {sentimentData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[entry.name as keyof typeof COLORS] || '#8884d8'}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: chartConfig.backgroundColor,
                  border: `1px solid ${chartConfig.gridColor}`,
                  color: chartConfig.textColor,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Priority Distribution */}
        <div className={clsx(
          'p-6 rounded-lg border',
          theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'
        )}>
          <h3 className={clsx(
            'text-lg font-semibold mb-4',
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          )}>
            By Priority
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={priorityData}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={chartConfig.gridColor}
              />
              <XAxis
                dataKey="name"
                stroke={chartConfig.textColor}
                style={{ fontSize: '12px' }}
              />
              <YAxis
                stroke={chartConfig.textColor}
                style={{ fontSize: '12px' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: chartConfig.backgroundColor,
                  border: `1px solid ${chartConfig.gridColor}`,
                  color: chartConfig.textColor,
                }}
              />
              <Bar dataKey="value" fill="#10b981" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

interface MetricCardProps {
  label: string
  value: string | number
  theme: 'light' | 'dark'
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, theme }) => (
  <div className={clsx(
    'p-4 rounded-lg border',
    theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'
  )}>
    <p className={clsx(
      'text-xs font-semibold mb-1 uppercase',
      theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
    )}>
      {label}
    </p>
    <p className={clsx(
      'text-2xl font-bold',
      theme === 'dark' ? 'text-white' : 'text-slate-900'
    )}>
      {value}
    </p>
  </div>
)

export default FeedbackVisualization
