import React, { useState, useEffect } from 'react';
import { Search, Download, Star, Users, AlertCircle, CheckCircle, Loader } from 'lucide-react';

interface Plugin {
  id: string;
  manifest: {
    name: string;
    version: string;
    description: string;
    description_zh: string;
    icon_url: string;
    screenshots: string[];
  };
  category: string;
  status: string;
  rating: number;
  rating_count: number;
  downloads: number;
  installed_count: number;
  is_installed: boolean;
  is_enabled: boolean;
  what_is_it: string;
  who_is_it_for: string;
  how_to_use: string;
  faq: Array<{ question: string; answer: string }>;
  tutorial: string;
}

interface Category {
  id: string;
  name: string;
  name_zh: string;
  icon: string;
  description: string;
  description_zh: string;
  plugin_count: number;
}

const PluginMarket: React.FC = () => {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null);
  const [loading, setLoading] = useState(false);
  const [installing, setInstalling] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState('rating');

  // 获取分类
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await fetch('/api/v1/plugin-market/categories');
        const data = await response.json();
        setCategories(data);
      } catch (error) {
        console.error('Failed to fetch categories:', error);
      }
    };
    fetchCategories();
  }, []);

  // 获取插件列表
  useEffect(() => {
    const fetchPlugins = async () => {
      setLoading(true);
      try {
        let url = '/api/v1/plugin-market/plugins?sort_by=' + sortBy;
        if (selectedCategory) {
          url += '&category=' + selectedCategory;
        }
        const response = await fetch(url);
        const data = await response.json();
        setPlugins(data);
      } catch (error) {
        console.error('Failed to fetch plugins:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchPlugins();
  }, [selectedCategory, sortBy]);

  // 搜索插件
  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      // 重新加载所有插件
      const response = await fetch('/api/v1/plugin-market/plugins');
      const data = await response.json();
      setPlugins(data);
      return;
    }

    try {
      const response = await fetch('/api/v1/plugin-market/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          category: selectedCategory,
          sort_by: sortBy,
          limit: 20,
          offset: 0,
        }),
      });
      const data = await response.json();
      setPlugins(data);
    } catch (error) {
      console.error('Failed to search plugins:', error);
    }
  };

  // 安装插件
  const handleInstall = async (pluginId: string) => {
    setInstalling(pluginId);
    try {
      const response = await fetch(`/api/v1/plugin-market/plugins/${pluginId}/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plugin_id: pluginId,
          auto_enable: true,
        }),
      });
      const _data = await response.json();

      // 更新插件状态
      setPlugins(plugins.map(p =>
        p.id === pluginId ? { ...p, is_installed: true, is_enabled: true } : p
      ));

      if (selectedPlugin?.id === pluginId) {
        setSelectedPlugin({ ...selectedPlugin, is_installed: true, is_enabled: true });
      }
    } catch (error) {
      console.error('Failed to install plugin:', error);
    } finally {
      setInstalling(null);
    }
  };

  // 卸载插件
  const handleUninstall = async (pluginId: string) => {
    try {
      const _response = await fetch(`/api/v1/plugin-market/plugins/${pluginId}/uninstall`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plugin_id: pluginId,
          remove_config: false,
        }),
      });

      // 更新插件状态
      setPlugins(plugins.map(p =>
        p.id === pluginId ? { ...p, is_installed: false, is_enabled: false } : p
      ));

      if (selectedPlugin?.id === pluginId) {
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
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* 左侧边栏 - 分类 */}
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
                    className={`w-full text-left px-4 py-2 rounded-lg transition flex items-center gap-2 ${
                      selectedCategory === cat.id
                        ? 'bg-blue-100 text-blue-900 font-semibold'
                        : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <span className="text-xl">{cat.icon}</span>
                    <div>
                      <div>{cat.name_zh}</div>
                      <div className="text-xs text-gray-500">{cat.plugin_count}个</div>
                    </div>
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
              // 插件详情页面
              <PluginDetail
                plugin={selectedPlugin}
                onBack={() => setSelectedPlugin(null)}
                onInstall={handleInstall}
                onUninstall={handleUninstall}
                installing={installing === selectedPlugin.id}
              />
            ) : (
              // 插件列表
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
                        key={plugin.id}
                        plugin={plugin}
                        onSelect={() => setSelectedPlugin(plugin)}
                        onInstall={handleInstall}
                        onUninstall={handleUninstall}
                        installing={installing === plugin.id}
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
            <h3 className="text-lg font-semibold text-gray-900">{plugin.manifest.name}</h3>
            <p className="text-sm text-gray-500 mt-1">v{plugin.manifest.version}</p>
          </div>
          {plugin.is_installed && (
            <CheckCircle className="text-green-500" size={24} />
          )}
        </div>

        <p className="text-gray-600 text-sm mb-4 line-clamp-2">
          {plugin.manifest.description_zh || plugin.manifest.description}
        </p>

        {/* 统计信息 */}
        <div className="flex items-center gap-4 text-sm text-gray-500">
          <div className="flex items-center gap-1">
            <Star size={16} className="text-yellow-400" />
            <span>{plugin.rating.toFixed(1)}</span>
            <span className="text-xs">({plugin.rating_count})</span>
          </div>
          <div className="flex items-center gap-1">
            <Download size={16} />
            <span>{plugin.downloads}</span>
          </div>
          <div className="flex items-center gap-1">
            <Users size={16} />
            <span>{plugin.installed_count}</span>
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
            onClick={() => onUninstall(plugin.id)}
            className="flex-1 px-4 py-2 bg-red-50 text-red-600 hover:bg-red-100 rounded-lg transition text-sm font-medium"
          >
            卸载
          </button>
        ) : (
          <button
            onClick={() => onInstall(plugin.id)}
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
  const [activeTab, setActiveTab] = useState<'overview' | 'tutorial' | 'faq'>('overview');

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
            <h1 className="text-3xl font-bold text-gray-900">{plugin.manifest.name}</h1>
            <p className="text-gray-600 mt-2">v{plugin.manifest.version}</p>
          </div>
          {plugin.is_installed && (
            <CheckCircle className="text-green-500" size={32} />
          )}
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-3">
          {plugin.is_installed ? (
            <button
              onClick={() => onUninstall(plugin.id)}
              className="px-6 py-2 bg-red-50 text-red-600 hover:bg-red-100 rounded-lg transition font-medium"
            >
              卸载
            </button>
          ) : (
            <button
              onClick={() => onInstall(plugin.id)}
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
          {(['overview', 'tutorial', 'faq'] as const).map((tab) => (
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
              {tab === 'tutorial' && '教程'}
              {tab === 'faq' && '常见问题'}
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
              <p className="text-gray-700 whitespace-pre-wrap">{plugin.what_is_it}</p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-2">适合谁用？</h2>
              <p className="text-gray-700 whitespace-pre-wrap">{plugin.who_is_it_for}</p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-2">怎么用？</h2>
              <p className="text-gray-700 whitespace-pre-wrap">{plugin.how_to_use}</p>
            </div>
          </div>
        )}

        {activeTab === 'tutorial' && (
          <div className="prose prose-sm max-w-none">
            <p className="text-gray-700 whitespace-pre-wrap">{plugin.tutorial}</p>
          </div>
        )}

        {activeTab === 'faq' && (
          <div className="space-y-4">
            {plugin.faq.map((item, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4">
                <h3 className="font-semibold text-gray-900 mb-2">{item.question}</h3>
                <p className="text-gray-700">{item.answer}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default PluginMarket;
