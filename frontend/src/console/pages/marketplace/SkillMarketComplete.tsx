import React, { useState, useEffect, useCallback } from 'react';
import { Search, Download, Star, Users, Zap, ChevronRight, Filter, Grid, List, Heart, Share2, AlertCircle } from 'lucide-react';

interface Skill {
  id: string;
  name: string;
  name_zh: string;
  version: string;
  category: string;
  rating: number;
  rating_count: number;
  downloads: number;
  installed_count: number;
  usage_count: number;
  is_installed: boolean;
  is_favorite: boolean;
  description_zh: string;
  icon_emoji: string;
  keywords: string[];
  tags: string[];
  what_is_it: string;
  who_is_it_for: string;
  how_to_use: string;
}

interface Category {
  id: string;
  name_zh: string;
  icon: string;
  skill_count: number;
}

interface MarketStats {
  total_skills: number;
  installed_skills: number;
  total_downloads: number;
  total_usage: number;
  average_rating: number;
  categories: Record<string, number>;
}

export const SkillMarketComplete: React.FC = () => {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [stats, setStats] = useState<MarketStats | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy] = useState('rating');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [installedSkills, setInstalledSkills] = useState<Set<string>>(new Set());
  const [favoriteSkills, setFavoriteSkills] = useState<Set<string>>(new Set());

  // 获取分类
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await fetch('/api/v1/skill-market/categories');
        const data = await response.json();
        setCategories(data);
      } catch (error) {
        console.error('获取分类失败:', error);
      }
    };
    fetchCategories();
  }, []);

  // 获取市场统计
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch('/api/v1/skill-market/stats');
        const data = await response.json();
        setStats(data);
      } catch (error) {
        console.error('获取统计失败:', error);
      }
    };
    fetchStats();
  }, []);

  // 获取已安装的技能
  useEffect(() => {
    const fetchInstalledSkills = async () => {
      try {
        const response = await fetch('/api/v1/skill-market/my-skills');
        const data = await response.json();
        setInstalledSkills(new Set(data.skills.map((s: any) => s.skill_id)));
      } catch (error) {
        console.error('获取已安装技能失败:', error);
      }
    };
    fetchInstalledSkills();
  }, []);

  // 获取技能列表
  useEffect(() => {
    const fetchSkills = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({
          limit: '20',
          sort_by: sortBy,
        });

        if (selectedCategory) {
          const url = `/api/v1/skill-market/categories/${selectedCategory}/skills?${params}`;
          const response = await fetch(url);
          const data = await response.json();
          setSkills(data.skills);
        } else {
          const response = await fetch(`/api/v1/skill-market/skills?${params}`);
          const data = await response.json();
          setSkills(data.skills);
        }
      } catch (error) {
        console.error('获取技能列表失败:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSkills();
  }, [selectedCategory, sortBy]);

  // 搜索技能
  const handleSearch = useCallback(async (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(
        `/api/v1/skill-market/skills/search?query=${encodeURIComponent(query)}`
      );
      const data = await response.json();
      setSkills(data.skills);
    } catch (error) {
      console.error('搜索失败:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // 安装技能
  const handleInstall = async (skillId: string) => {
    try {
      const response = await fetch(`/api/v1/skill-market/skills/${skillId}/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_id: skillId }),
      });

      if (response.ok) {
        setInstalledSkills(new Set([...installedSkills, skillId]));
        setSkills(skills.map(s =>
          s.id === skillId ? { ...s, is_installed: true } : s
        ));
        if (selectedSkill?.id === skillId) {
          setSelectedSkill({ ...selectedSkill, is_installed: true });
        }
      }
    } catch (error) {
      console.error('安装失败:', error);
    }
  };

  // 卸载技能
  const handleUninstall = async (skillId: string) => {
    try {
      const response = await fetch(`/api/v1/skill-market/skills/${skillId}/uninstall`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (response.ok) {
        installedSkills.delete(skillId);
        setInstalledSkills(new Set(installedSkills));
        setSkills(skills.map(s =>
          s.id === skillId ? { ...s, is_installed: false } : s
        ));
        if (selectedSkill?.id === skillId) {
          setSelectedSkill({ ...selectedSkill, is_installed: false });
        }
      }
    } catch (error) {
      console.error('卸载失败:', error);
    }
  };

  // 收藏技能
  const handleFavorite = (skillId: string) => {
    if (favoriteSkills.has(skillId)) {
      favoriteSkills.delete(skillId);
    } else {
      favoriteSkills.add(skillId);
    }
    setFavoriteSkills(new Set(favoriteSkills));
  };

  // 技能卡片组件
  const SkillCard: React.FC<{ skill: Skill }> = ({ skill }) => (
    <div
      className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow p-4 cursor-pointer"
      onClick={() => {
        setSelectedSkill(skill);
        setShowDetailModal(true);
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="text-3xl">{skill.icon_emoji}</div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleFavorite(skill.id);
          }}
          className={`p-1 rounded-full ${
            favoriteSkills.has(skill.id)
              ? 'bg-red-100 text-red-600'
              : 'bg-gray-100 text-gray-600'
          }`}
        >
          <Heart size={16} fill={favoriteSkills.has(skill.id) ? 'currentColor' : 'none'} />
        </button>
      </div>

      <h3 className="font-semibold text-gray-900 mb-1">{skill.name_zh}</h3>
      <p className="text-sm text-gray-600 mb-3 line-clamp-2">{skill.description_zh}</p>

      <div className="flex items-center gap-2 mb-3 text-sm text-gray-600">
        <Star size={14} className="text-yellow-500" />
        <span>{skill.rating.toFixed(1)}</span>
        <span className="text-gray-400">({skill.rating_count})</span>
        <span className="ml-auto">{skill.downloads} 下载</span>
      </div>

      <div className="flex gap-2">
        {skill.is_installed ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleUninstall(skill.id);
            }}
            className="flex-1 px-3 py-2 bg-gray-200 text-gray-800 rounded text-sm font-medium hover:bg-gray-300"
          >
            已安装
          </button>
        ) : (
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleInstall(skill.id);
            }}
            className="flex-1 px-3 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700"
          >
            安装
          </button>
        )}
      </div>
    </div>
  );

  // 技能详情模态框
  const SkillDetailModal: React.FC = () => {
    if (!selectedSkill) return null;

    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          <div className="sticky top-0 bg-white border-b p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-4xl">{selectedSkill.icon_emoji}</span>
              <div>
                <h2 className="text-2xl font-bold text-gray-900">{selectedSkill.name_zh}</h2>
                <p className="text-sm text-gray-600">v{selectedSkill.version}</p>
              </div>
            </div>
            <button
              onClick={() => setShowDetailModal(false)}
              className="text-gray-500 hover:text-gray-700"
            >
              ✕
            </button>
          </div>

          <div className="p-6 space-y-6">
            {/* 统计信息 */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-blue-50 p-3 rounded-lg text-center">
                <div className="text-2xl font-bold text-blue-600">{selectedSkill.rating.toFixed(1)}</div>
                <div className="text-xs text-gray-600">评分</div>
              </div>
              <div className="bg-green-50 p-3 rounded-lg text-center">
                <div className="text-2xl font-bold text-green-600">{selectedSkill.downloads}</div>
                <div className="text-xs text-gray-600">下载</div>
              </div>
              <div className="bg-purple-50 p-3 rounded-lg text-center">
                <div className="text-2xl font-bold text-purple-600">{selectedSkill.installed_count}</div>
                <div className="text-xs text-gray-600">已安装</div>
              </div>
              <div className="bg-orange-50 p-3 rounded-lg text-center">
                <div className="text-2xl font-bold text-orange-600">{selectedSkill.usage_count}</div>
                <div className="text-xs text-gray-600">使用次数</div>
              </div>
            </div>

            {/* 描述 */}
            <div>
              <h3 className="font-semibold text-gray-900 mb-2">这个技能是干什么的？</h3>
              <p className="text-gray-700">{selectedSkill.what_is_it || selectedSkill.description_zh}</p>
            </div>

            {/* 适用人群 */}
            <div>
              <h3 className="font-semibold text-gray-900 mb-2">适合谁用？</h3>
              <p className="text-gray-700">{selectedSkill.who_is_it_for || '所有用户'}</p>
            </div>

            {/* 使用方法 */}
            <div>
              <h3 className="font-semibold text-gray-900 mb-2">怎么用？</h3>
              <p className="text-gray-700">{selectedSkill.how_to_use || '按照提示步骤操作'}</p>
            </div>

            {/* 标签 */}
            {selectedSkill.keywords.length > 0 && (
              <div>
                <h3 className="font-semibold text-gray-900 mb-2">关键词</h3>
                <div className="flex flex-wrap gap-2">
                  {selectedSkill.keywords.map((keyword) => (
                    <span
                      key={keyword}
                      className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* 操作按钮 */}
            <div className="flex gap-3 pt-4 border-t">
              {selectedSkill.is_installed ? (
                <button
                  onClick={() => handleUninstall(selectedSkill.id)}
                  className="flex-1 px-4 py-2 bg-gray-200 text-gray-800 rounded font-medium hover:bg-gray-300"
                >
                  卸载
                </button>
              ) : (
                <button
                  onClick={() => handleInstall(selectedSkill.id)}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded font-medium hover:bg-blue-700"
                >
                  安装
                </button>
              )}
              <button
                onClick={() => handleFavorite(selectedSkill.id)}
                className={`px-4 py-2 rounded font-medium ${
                  favoriteSkills.has(selectedSkill.id)
                    ? 'bg-red-100 text-red-600 hover:bg-red-200'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                <Heart size={18} fill={favoriteSkills.has(selectedSkill.id) ? 'currentColor' : 'none'} />
              </button>
              <button className="px-4 py-2 bg-gray-100 text-gray-600 rounded font-medium hover:bg-gray-200">
                <Share2 size={18} />
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* 头部 */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">技能市场</h1>
          <p className="text-gray-600">发现和使用强大的AI技能，提高工作效率</p>

          {/* 统计信息 */}
          {stats && (
            <div className="grid grid-cols-4 gap-4 mt-6">
              <div className="bg-blue-50 p-4 rounded-lg">
                <div className="text-2xl font-bold text-blue-600">{stats.total_skills}</div>
                <div className="text-sm text-gray-600">总技能数</div>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <div className="text-2xl font-bold text-green-600">{stats.installed_skills}</div>
                <div className="text-sm text-gray-600">已安装</div>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg">
                <div className="text-2xl font-bold text-purple-600">{stats.total_downloads}</div>
                <div className="text-sm text-gray-600">总下载</div>
              </div>
              <div className="bg-orange-50 p-4 rounded-lg">
                <div className="text-2xl font-bold text-orange-600">{stats.average_rating.toFixed(1)}</div>
                <div className="text-sm text-gray-600">平均评分</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 搜索和过滤 */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex gap-4 mb-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-3 text-gray-400" size={20} />
              <input
                type="text"
                placeholder="搜索技能..."
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="rating">按评分</option>
              <option value="downloads">按下载</option>
              <option value="newest">最新</option>
            </select>
            <div className="flex gap-2">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 rounded ${viewMode === 'grid' ? 'bg-blue-100 text-blue-600' : 'bg-gray-100'}`}
              >
                <Grid size={20} />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 rounded ${viewMode === 'list' ? 'bg-blue-100 text-blue-600' : 'bg-gray-100'}`}
              >
                <List size={20} />
              </button>
            </div>
          </div>

          {/* 分类过滤 */}
          <div className="flex gap-2 overflow-x-auto pb-2">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`px-4 py-2 rounded-full whitespace-nowrap ${
                selectedCategory === null
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              全部
            </button>
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`px-4 py-2 rounded-full whitespace-nowrap ${
                  selectedCategory === cat.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {cat.icon} {cat.name_zh}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 技能列表 */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="mt-4 text-gray-600">加载中...</p>
          </div>
        ) : skills.length === 0 ? (
          <div className="text-center py-12">
            <AlertCircle size={48} className="mx-auto text-gray-400 mb-4" />
            <p className="text-gray-600">未找到匹配的技能</p>
          </div>
        ) : (
          <div
            className={
              viewMode === 'grid'
                ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4'
                : 'space-y-4'
            }
          >
            {skills.map((skill) => (
              <SkillCard key={skill.id} skill={skill} />
            ))}
          </div>
        )}
      </div>

      {/* 详情模态框 */}
      {showDetailModal && <SkillDetailModal />}
    </div>
  );
};

export default SkillMarketComplete;
