import React, { useState, useEffect, useMemo } from 'react';
import { Search, Download, Star, Users, AlertCircle, CheckCircle, Loader } from 'lucide-react';

/**
 * B8 修复：插件市场数据层对齐后端真实路由 /api/v1/plugin-ecosystem
 * （backend/app/api/plugin_marketplace.py 已在 main.py 注册）。
 * 原来的 /api/v1/plugin-market/*（plugin_market.py）未注册，不可达。
 *
 * 后端真实模型（PluginListing.to_dict）：
 *   plugin_id, name, version, description, author, category, status,
 *   risk_level, risk_score, rating, rating_count, downloads, installed_count,
 *   is_installed, is_enabled, created_at, published_at
 * 详情端点额外返回：permissions, dependencies, reviews[]。
 * 后端无分类端点 → 分类由插件列表的 category 字段前端聚合。
 */
interface Plugin {
  plugin_id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  category: string;
  status: string;
  risk_level?: string;
  rating: number;
  rating_count: number;
  downloads: number;
  installed_count: number;
  is_installed: boolean;
  is_enabled: boolean;
  published_at?: string | null;
  // 详情端点附加字段
  permissions?: string[];
  dependencies?: string[];
  reviews?: Array<{ rating: number; comment: string; user_id: string; created_at: string }>;
}

const API_BASE = '/api/v1/plugin-ecosystem';

const CATEGORY_LABELS: Record<string, string> = {
  development: '开发工具',
  data: '数据处理',
  automation: '自动化',
  integration: '集成',
  security: '安全',
  productivity: '效率',
  other: '其他',
};

const PluginMarket: React.FC = () => {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null);
  const [loading, setLoading] = useState(false);
  const [installing, setInstalling] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState('rating');

  // 分类：由插件列表的 category 字段聚合（后端无独立分类端点）
  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    for (const plugin of plugins) {
      const key = plugin.category || 'other';
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return [...counts.entries()].map(([id, count]) => ({
      id,
      label: CATEGORY_LABELS[id] ?? id,
      count,
    }));
  }, [plugins]);

  // 获取插件列表（B8：真实端点，支持 query/category/sort_by/limit）
  useEffect(() => {
    const fetchPlugins = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({ sort_by: sortBy, limit: '50' });
        if (selectedCategory) params.set('category', selectedCategory);
        if (searchQuery.trim()) params.set('query', searchQuery.trim());
        const response = await fetch(`${API_BASE}/plugins?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = (await response.json()) as Plugin[];
        setPlugins(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Failed to fetch plugins:', error);
      } finally {
        setLoading(false);
      }
    };
    const timer = setTimeout(fetchPlugins, searchQuery ? 300 : 0);
    return () => clearTimeout(timer);
  }, [selectedCategory, sortBy, searchQuery]);

  // 打开详情：拉取详情端点（含 permissions/dependencies/reviews）
  const handleSelectPlugin = async (plugin: Plugin) => {
    setSelectedPlugin(plugin);
    try {
      const response = await fetch(`${API_BASE}/plugins/${encodeURIComponent(plugin.plugin_id)}`);
      if (!response.ok) return;
      const detail = (await response.json()) as Plugin;
      setSelectedPlugin((current) => (current?.plugin_id === plugin.plugin_id ? { ...current, ...detail } : current));
    } catch (error) {
      console.error('Failed to fetch plugin detail:', error);
    }
  };

  // 安装插件（B8：真实端点，无请求体）
  const handleInstall = async (pluginId: string) => {
    setInstalling(pluginId);
    try {
      const response = await fetch(`${API_BASE}/plugins/${encodeURIComponent(pluginId)}/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      setPlugins(plugins.map((p) =>
        p.plugin_id === pluginId ? { ...p, is_installed: true, is_enabled: true } : p,
      ));
      if (selectedPlugin?.plugin_id === pluginId) {
        setSelectedPlugin({ ...selectedPlugin, is_installed: true, is_enabled: true });
      }
    } catch (error) {
      console.error('Failed to install plugin:', error);
    } finally {
      setInstalling(null);
    }
  };

  // 卸载插件（B8：真实端点，无请求体）
  const handleUninstall = async (pluginId: string) => {
    try {
      const response = await fetch(`${API_BASE}/plugins/${encodeURIComponent(pluginId)}/uninstall`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      setPlugins(plugins.map((p) =>
        p.plugin_id === pluginId ? { ...p, is_installed: false, is_enabled: false } : p,
      ));
      if (selectedPlugin?.plugin_id === pluginId) {
        setSelectedPlugin({ ...selectedPlugin, is_installed: false, is_enabled: false });
      }
    } catch (error) {
      console.error('Failed to uninstall plugin:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* 头部 */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">插件市场</h1>
          <p className="text-gray-600">发现和安装强大的插件，扩展X-Agent的功能</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 搜索栏 */}
        <div className="mb-8">
          <div className="relative">
            <Search className="absolute left-3 top-3 text-gray-400" size={20} />
            <input
              type="text"
              placeholder="搜索插件..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* 左侧边栏 - 分类（前端聚合） */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-sm p-6 sticky top-4">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">分类</h2>
              <div className="space-y-2">
                <button
                  onClick={() => setSelectedCategory(null)}
                  className={`w-full text-left px-4 py-2 rounded-lg transition ${
                    selectedCategory === null
                      ? 'bg-blue-100 text-blue-900 font-semibold'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  全部
                </button>
                {categories.map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                    className={`w-full text-left px-4 py-2 rounded-lg transition flex items-center justify-between ${
                      selectedCategory === cat.id
                        ? 'bg-blue-100 text-blue-900 font-semibold'
                        : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <span>{cat.label}</span>
                    <span className="text-xs text-gray-500">{cat.count}个</span>
                  </button>
                ))}
              </div>

              {/* 排序 */}
              <div className="mt-6 pt-6 border-t border-gray-200">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">排序</h3>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="rating">评分最高</option>
                  <option value="downloads">下载最多</option>
                  <option value="newest">最新发布</option>
                </select>
              </div>
            </div>
          </div>

          {/* 右侧 - 插件列表或详情 */}
          <div className="lg:col-span-3">
            {selectedPlugin ? (
              <PluginDetail
                plugin={selectedPlugin}
                onBack={() => setSelectedPlugin(null)}
                onInstall={handleInstall}
                onUninstall={handleUninstall}
                installing={installing === selectedPlugin.plugin_id}
              />
            ) : (
              <div>
                {loading ? (
                  <div className="flex justify-center items-center h-64">
                    <Loader className="animate-spin text-blue-500" size={32} />
                  </div>
                ) : plugins.length === 0 ? (
                  <div className="text-center py-12">
                    <AlertCircle className="mx-auto text-gray-400 mb-4" size={48} />
                    <p className="text-gray-600">未找到插件</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {plugins.map((plugin) => (
                      <PluginCard
                        key={plugin.plugin_id}
                        plugin={plugin}
                        onSelect={() => handleSelectPlugin(plugin)}
                        onInstall={handleInstall}
                        onUninstall={handleUninstall}
                        installing={installing === plugin.plugin_id}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

interface PluginCardProps {
  plugin: Plugin;
  onSelect: () => void;
  onInstall: (id: string) => void;
  onUninstall: (id: string) => void;
  installing: boolean;
}

const PluginCard: React.FC<PluginCardProps> = ({
  plugin,
  onSelect,
  onInstall,
  onUninstall,
  installing,
}) => {
  return (
    <div className="bg-white rounded-lg shadow-sm hover:shadow-md transition overflow-hidden">
      {/* 卡片头部 */}
      <div
        role="button"
        tabIndex={0}
        className="p-6 cursor-pointer hover:bg-gray-50"
        onClick={onSelect}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect?.(); }}
      >
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-900">{plugin.name}</h3>
            <p className="text-sm text-gray-500 mt-1">v{plugin.version} · {CATEGORY_LABELS[plugin.category] ?? plugin.category}</p>
          </div>
          {plugin.is_installed && (
            <CheckCircle className="text-green-500" size={24} />
          )}
        </div>

        <p className="text-gray-600 text-sm mb-4 line-clamp-2">
          {plugin.description}
        </p>

        {/* 统计信息 */}
        <div className="flex items-center gap-4 text-sm text-gray-500">
          <div className="flex items-center gap-1">
            <Star size={16} className="text-yellow-400" />
            <span>{(plugin.rating ?? 0).toFixed(1)}</span>
            <span className="text-xs">({plugin.rating_count ?? 0})</span>
          </div>
          <div className="flex items-center gap-1">
            <Download size={16} />
            <span>{plugin.downloads ?? 0}</span>
          </div>
          <div className="flex items-center gap-1">
            <Users size={16} />
            <span>{plugin.installed_count ?? 0}</span>
          </div>
        </div>
      </div>

      {/* 卡片底部 - 操作按钮 */}
      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex gap-2">
        <button
          onClick={onSelect}
          className="flex-1 px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition text-sm font-medium"
        >
          查看详情
        </button>
        {plugin.is_installed ? (
          <button
            onClick={() => onUninstall(plugin.plugin_id)}
            className="flex-1 px-4 py-2 bg-red-50 text-red-600 hover:bg-red-100 rounded-lg transition text-sm font-medium"
          >
            卸载
          </button>
        ) : (
          <button
            onClick={() => onInstall(plugin.plugin_id)}
            disabled={installing}
            className="flex-1 px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {installing ? (
              <>
                <Loader size={16} className="animate-spin" />
                安装中...
              </>
            ) : (
              <>
                <Download size={16} />
                一键安装
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
};

interface PluginDetailProps {
  plugin: Plugin;
  onBack: () => void;
  onInstall: (id: string) => void;
  onUninstall: (id: string) => void;
  installing: boolean;
}

const PluginDetail: React.FC<PluginDetailProps> = ({
  plugin,
  onBack,
  onInstall,
  onUninstall,
  installing,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'permissions' | 'reviews'>('overview');

  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      {/* 头部 */}
      <div className="p-6 border-b border-gray-200">
        <button
          onClick={onBack}
          className="text-blue-600 hover:text-blue-700 text-sm font-medium mb-4"
        >
          ← 返回列表
        </button>

        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{plugin.name}</h1>
            <p className="text-gray-600 mt-2">v{plugin.version} · {plugin.author || '未知作者'}</p>
          </div>
          {plugin.is_installed && (
            <CheckCircle className="text-green-500" size={32} />
          )}
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-3">
          {plugin.is_installed ? (
            <button
              onClick={() => onUninstall(plugin.plugin_id)}
              className="px-6 py-2 bg-red-50 text-red-600 hover:bg-red-100 rounded-lg transition font-medium"
            >
              卸载
            </button>
          ) : (
            <button
              onClick={() => onInstall(plugin.plugin_id)}
              disabled={installing}
              className="px-6 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition font-medium disabled:opacity-50 flex items-center gap-2"
            >
              {installing ? (
                <>
                  <Loader size={18} className="animate-spin" />
                  安装中...
                </>
              ) : (
                <>
                  <Download size={18} />
                  一键安装
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* 标签页 */}
      <div className="border-b border-gray-200">
        <div className="flex">
          {(['overview', 'permissions', 'reviews'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-6 py-3 font-medium transition ${
                activeTab === tab
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab === 'overview' && '概览'}
              {tab === 'permissions' && '权限与依赖'}
              {tab === 'reviews' && '评价'}
            </button>
          ))}
        </div>
      </div>

      {/* 内容 */}
      <div className="p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-2">这个插件是干什么的？</h2>
              <p className="text-gray-700 whitespace-pre-wrap">{plugin.description || '暂无描述'}</p>
            </div>

            <div className="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded-lg text-sm">
              <div>分类：{CATEGORY_LABELS[plugin.category] ?? plugin.category}</div>
              <div>状态：{plugin.status}</div>
              <div>风险等级：{plugin.risk_level ?? '-'}</div>
              <div>发布时间：{plugin.published_at ?? '-'}</div>
            </div>
          </div>
        )}

        {activeTab === 'permissions' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-2">所需权限</h2>
              {plugin.permissions?.length ? (
                <div className="flex flex-wrap gap-2">
                  {plugin.permissions.map((permission) => (
                    <span key={permission} className="bg-gray-100 text-gray-700 px-3 py-1 rounded-full text-sm">{permission}</span>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">无需特殊权限</p>
              )}
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-2">依赖</h2>
              {plugin.dependencies?.length ? (
                <div className="flex flex-wrap gap-2">
                  {plugin.dependencies.map((dependency) => (
                    <span key={dependency} className="bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-sm">{dependency}</span>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">无外部依赖</p>
              )}
            </div>
          </div>
        )}

        {activeTab === 'reviews' && (
          <div className="space-y-4">
            {plugin.reviews?.length ? plugin.reviews.map((review, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Star size={16} className="text-yellow-400" />
                  <span className="font-semibold text-gray-900">{review.rating}/5</span>
                  <span className="text-xs text-gray-500">{review.user_id} · {review.created_at}</span>
                </div>
                <p className="text-gray-700">{review.comment || '（无评价内容）'}</p>
              </div>
            )) : (
              <p className="text-gray-500 text-sm">暂无评价</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default PluginMarket;
