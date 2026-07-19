import React, { useState, useEffect } from 'react';
import { Search, Download, Star, Users, Zap, ChevronRight } from 'lucide-react';

interface Skill {
  id: string;
  manifest: {
    name: string;
    name_zh: string;
    description_zh: string;
    icon_emoji: string;
    keywords: string[];
  };
  category: string;
  rating: number;
  downloads: number;
  installed_count: number;
  is_installed: boolean;
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

export const SkillMarket: React.FC = () => {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy] = useState('rating');

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
          params.append('category', selectedCategory);
        }

        const response = await fetch(`/api/v1/skill-market/skills?${params}`);
        const data = await response.json();
        setSkills(data.skills);
      } catch (error) {
        console.error('获取技能列表失败:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSkills();
  }, [selectedCategory, sortBy]);

  // 搜索技能
  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(
        `/api/v1/skill-market/search?query=${encodeURIComponent(query)}`
      );
      const data = await response.json();
      setSkills(data.results);
    } catch (error) {
      console.error('搜索失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 安装技能
  const handleInstall = async (skillId: string) => {
    try {
      const response = await fetch(`/api/v1/skill-market/skills/${skillId}/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_id: skillId }),
      });

      if (response.ok) {
        // 更新技能状态
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

  // 执行技能
  const handleExecute = async (skillId: string) => {
    try {
      const response = await fetch(`/api/v1/skill-market/skills/${skillId}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_id: skillId, input_data: {} }),
      });

      if (response.ok) {
        alert('技能执行成功！');
      }
    } catch (error) {
      console.error('执行失败:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* 头部 */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">技能市场</h1>
          <p className="text-gray-600">发现和使用强大的AI技能，提高工作效率</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 搜索栏 */}
        <div className="mb-8">
          <div className="relative">
            <Search className="absolute left-3 top-3 text-gray-400" size={20} />
            <input
              type="text"
              placeholder="搜索技能... 例如：代码审查、数据分析"
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* 左侧：分类导航 */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-sm p-6 sticky top-4">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">分类</h2>
              <div className="space-y-2">
                <button
                  onClick={() => setSelectedCategory(null)}
                  className={`w-full text-left px-4 py-2 rounded-lg transition ${
                    selectedCategory === null
                      ? 'bg-blue-100 text-blue-700 font-semibold'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  全部技能
                </button>
                {categories.map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                    className={`w-full text-left px-4 py-2 rounded-lg transition flex items-center justify-between ${
                      selectedCategory === cat.id
                        ? 'bg-blue-100 text-blue-700 font-semibold'
                        : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <span>
                      {cat.icon} {cat.name_zh}
                    </span>
                    <span className="text-sm text-gray-500">({cat.skill_count})</span>
                  </button>
                ))}
              </div>

              {/* 排序选项 */}
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
                  <option value="usage">使用最多</option>
                </select>
              </div>
            </div>
          </div>

          {/* 右侧：技能列表 */}
          <div className="lg:col-span-3">
            {loading ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                <p className="mt-4 text-gray-600">加载中...</p>
              </div>
            ) : skills.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-lg">
                <p className="text-gray-600">暂无技能</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {skills.map((skill) => (
                  <div
                    key={skill.id}
                    className="bg-white rounded-lg shadow-sm hover:shadow-md transition cursor-pointer overflow-hidden"
                    onClick={() => setSelectedSkill(skill)}
                  >
                    {/* 技能卡片头部 */}
                    <div className="bg-gradient-to-r from-blue-500 to-indigo-600 p-4 text-white">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <span className="text-3xl">{skill.manifest.icon_emoji}</span>
                          <div>
                            <h3 className="font-semibold text-lg">{skill.manifest.name_zh}</h3>
                            <p className="text-sm text-blue-100">{skill.manifest.name}</p>
                          </div>
                        </div>
                        {skill.is_installed && (
                          <span className="bg-green-500 text-white px-2 py-1 rounded text-xs font-semibold">
                            已安装
                          </span>
                        )}
                      </div>
                    </div>

                    {/* 技能卡片内容 */}
                    <div className="p-4">
                      <p className="text-gray-700 text-sm mb-3 line-clamp-2">
                        {skill.manifest.description_zh}
                      </p>

                      {/* 统计信息 */}
                      <div className="flex items-center gap-4 text-sm text-gray-600 mb-4">
                        <div className="flex items-center gap-1">
                          <Star size={16} className="text-yellow-500" />
                          <span>{skill.rating.toFixed(1)}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Download size={16} className="text-blue-500" />
                          <span>{skill.downloads}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Users size={16} className="text-green-500" />
                          <span>{skill.installed_count}</span>
                        </div>
                      </div>

                      {/* 标签 */}
                      <div className="flex flex-wrap gap-2 mb-4">
                        {skill.manifest.keywords.slice(0, 3).map((keyword) => (
                          <span
                            key={keyword}
                            className="bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs"
                          >
                            {keyword}
                          </span>
                        ))}
                      </div>

                      {/* 按钮 */}
                      <div className="flex gap-2">
                        {!skill.is_installed ? (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleInstall(skill.id);
                            }}
                            className="flex-1 bg-blue-500 hover:bg-blue-600 text-white py-2 rounded-lg font-semibold transition"
                          >
                            安装
                          </button>
                        ) : (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleExecute(skill.id);
                            }}
                            className="flex-1 bg-green-500 hover:bg-green-600 text-white py-2 rounded-lg font-semibold transition flex items-center justify-center gap-2"
                          >
                            <Zap size={16} />
                            一键使用
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedSkill(skill);
                          }}
                          className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
                        >
                          <ChevronRight size={16} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 技能详情模态框 */}
      {selectedSkill && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
          onClick={() => setSelectedSkill(null)}
        >
          <div
            className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 详情头部 */}
            <div className="bg-gradient-to-r from-blue-500 to-indigo-600 p-6 text-white">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <span className="text-5xl">{selectedSkill.manifest.icon_emoji}</span>
                  <div>
                    <h2 className="text-2xl font-bold">{selectedSkill.manifest.name_zh}</h2>
                    <p className="text-blue-100">{selectedSkill.manifest.name}</p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedSkill(null)}
                  className="text-white hover:text-blue-100 text-2xl"
                >
                  ×
                </button>
              </div>
            </div>

            {/* 详情内容 */}
            <div className="p-6 space-y-6">
              {/* 这个技能是干什么的 */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">这个技能是干什么的？</h3>
                <p className="text-gray-700 whitespace-pre-wrap">{selectedSkill.what_is_it}</p>
              </div>

              {/* 适合谁用 */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">适合谁用？</h3>
                <p className="text-gray-700 whitespace-pre-wrap">{selectedSkill.who_is_it_for}</p>
              </div>

              {/* 怎么用 */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">怎么用？</h3>
                <p className="text-gray-700 whitespace-pre-wrap">{selectedSkill.how_to_use}</p>
              </div>

              {/* 统计信息 */}
              <div className="grid grid-cols-4 gap-4 bg-gray-50 p-4 rounded-lg">
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">{selectedSkill.rating.toFixed(1)}</div>
                  <div className="text-sm text-gray-600">评分</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">{selectedSkill.downloads}</div>
                  <div className="text-sm text-gray-600">下载</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-purple-600">{selectedSkill.installed_count}</div>
                  <div className="text-sm text-gray-600">安装</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-orange-600">{selectedSkill.manifest.keywords.length}</div>
                  <div className="text-sm text-gray-600">标签</div>
                </div>
              </div>

              {/* 按钮 */}
              <div className="flex gap-3">
                {!selectedSkill.is_installed ? (
                  <button
                    onClick={() => handleInstall(selectedSkill.id)}
                    className="flex-1 bg-blue-500 hover:bg-blue-600 text-white py-3 rounded-lg font-semibold transition"
                  >
                    安装技能
                  </button>
                ) : (
                  <button
                    onClick={() => handleExecute(selectedSkill.id)}
                    className="flex-1 bg-green-500 hover:bg-green-600 text-white py-3 rounded-lg font-semibold transition flex items-center justify-center gap-2"
                  >
                    <Zap size={18} />
                    一键使用
                  </button>
                )}
                <button
                  onClick={() => setSelectedSkill(null)}
                  className="flex-1 border border-gray-300 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-50 transition"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SkillMarket;
