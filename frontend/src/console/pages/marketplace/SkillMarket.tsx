import React, { useState, useEffect, useMemo } from 'react';
import { Search, Download, Star, Users, Zap, ChevronRight } from 'lucide-react';

/**
 * B9 修复：技能市场数据层对齐后端真实路由。
 * 原来的 /api/v1/skill-market/*（skill_market.py 等）未在 main.py 注册，不可达。
 *
 * 真实端点：
 * - /api/skills                      （skills_api.py，已注册）列表/搜索/安装/卸载/执行
 * - /api/v1/skill-sediment/*         （skill_sediment.py，已注册）技能自沉淀
 *
 * 注意：/api/skills 需要 RBAC scope（tools:read / tools:* / agent:run），
 * 本地开发匿名主体可用；生产环境需携带凭证，否则 401（页面按失败兜底处理）。
 */

/** 列表端点返回的技能记录（SkillMetadata.to_dict 的页面使用子集） */
interface SkillRecord {
  skill_id: string;
  name: string;
  version?: string;
  description?: string;
  author?: string;
  capabilities?: string[];
  tags?: string[];
  risk_level?: string;
  rating?: number;
  downloads?: number;
}

/** 页面统一视图模型 */
interface SkillView {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  capabilities: string[];
  tags: string[];
  rating: number;
  downloads: number;
  is_installed: boolean;
}

interface SedimentStats {
  total_events: number;
  sedimented_count: number;
  trajectory_buffer_size: number;
  total_skills: number;
  promoted: number;
  rejected: number;
  pruned: number;
}

interface SedimentSkill {
  name?: string;
  skill_name?: string;
  status?: string;
  usage_count?: number;
  description?: string;
  [key: string]: unknown;
}

const SKILLS_API = '/api/skills';
const SEDIMENT_API = '/api/v1/skill-sediment';

function toSkillView(record: SkillRecord, installedIds: Set<string>): SkillView {
  return {
    id: record.skill_id,
    name: record.name,
    version: record.version ?? '1.0.0',
    description: record.description ?? '',
    author: record.author ?? '',
    capabilities: record.capabilities ?? [],
    tags: record.tags ?? [],
    rating: record.rating ?? 0,
    downloads: record.downloads ?? 0,
    is_installed: installedIds.has(record.skill_id) || installedIds.has(record.name),
  };
}

export const SkillMarket: React.FC = () => {
  const [skills, setSkills] = useState<SkillView[]>([]);
  const [installedIds, setInstalledIds] = useState<Set<string>>(new Set());
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSkill, setSelectedSkill] = useState<SkillView | null>(null);
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy] = useState('rating');
  const [sedimentStats, setSedimentStats] = useState<SedimentStats | null>(null);
  const [sedimentDrafts, setSedimentDrafts] = useState<SedimentSkill[]>([]);

  // 获取已安装技能（B9：GET /api/skills?installed_only=true）
  useEffect(() => {
    const fetchInstalled = async () => {
      try {
        const response = await fetch(`${SKILLS_API}?installed_only=true`);
        if (!response.ok) return;
        const data = await response.json();
        const items = Array.isArray(data.skills) ? data.skills : [];
        setInstalledIds(new Set(items.map((item: unknown) => {
          if (typeof item === 'string') return item;
          const record = item as { skill_id?: string; name?: string };
          return record.skill_id ?? record.name ?? '';
        }).filter(Boolean)));
      } catch (error) {
        console.error('获取已安装技能失败:', error);
      }
    };
    fetchInstalled();
  }, []);

  // 获取技能列表（B9：GET /api/skills；搜索走 GET /api/skills/search）
  useEffect(() => {
    const fetchSkills = async () => {
      setLoading(true);
      try {
        if (searchQuery.trim()) {
          const response = await fetch(`${SKILLS_API}/search?query=${encodeURIComponent(searchQuery.trim())}&limit=20`);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const data = await response.json();
          const results = Array.isArray(data.results) ? data.results : [];
          setSkills(results.map((record: SkillRecord) => toSkillView(record, installedIds)));
          return;
        }
        const response = await fetch(SKILLS_API);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        const records = Array.isArray(data.skills) ? data.skills : [];
        setSkills(records.map((record: SkillRecord) => toSkillView(record, installedIds)));
      } catch (error) {
        console.error('获取技能列表失败:', error);
      } finally {
        setLoading(false);
      }
    };
    const timer = setTimeout(fetchSkills, searchQuery ? 300 : 0);
    return () => clearTimeout(timer);
  }, [searchQuery, installedIds]);

  // 技能沉淀统计与草稿（B9：/api/v1/skill-sediment/*）
  const loadSediment = async () => {
    try {
      const [statsRes, draftsRes] = await Promise.all([
        fetch(`${SEDIMENT_API}/stats`),
        fetch(`${SEDIMENT_API}/skills?status=draft`),
      ]);
      if (statsRes.ok) setSedimentStats((await statsRes.json()) as SedimentStats);
      if (draftsRes.ok) {
        const drafts = await draftsRes.json();
        setSedimentDrafts(Array.isArray(drafts) ? drafts : []);
      }
    } catch (error) {
      console.error('获取技能沉淀数据失败:', error);
    }
  };

  useEffect(() => {
    loadSediment();
  }, []);

  // 分类：由技能 capabilities 前端聚合（后端无分类端点）
  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    for (const skill of skills) {
      for (const capability of skill.capabilities.length ? skill.capabilities : ['general']) {
        counts.set(capability, (counts.get(capability) ?? 0) + 1);
      }
    }
    return [...counts.entries()].map(([id, count]) => ({ id, count }));
  }, [skills]);

  // 过滤 + 排序（后端列表端点不支持 sort_by/category，前端处理）
  const visibleSkills = useMemo(() => {
    let result = skills;
    if (selectedCategory) {
      result = result.filter((skill) =>
        skill.capabilities.includes(selectedCategory) || (selectedCategory === 'general' && skill.capabilities.length === 0),
      );
    }
    const sorted = [...result];
    if (sortBy === 'rating') sorted.sort((a, b) => b.rating - a.rating);
    if (sortBy === 'downloads') sorted.sort((a, b) => b.downloads - a.downloads);
    if (sortBy === 'newest') sorted.sort((a, b) => a.name.localeCompare(b.name));
    return sorted;
  }, [skills, selectedCategory, sortBy]);

  // 安装技能（B9：POST /api/skills/{id}/install）
  const handleInstall = async (skillId: string) => {
    try {
      const response = await fetch(`${SKILLS_API}/${encodeURIComponent(skillId)}/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_id: skillId }),
      });

      if (response.ok) {
        setInstalledIds(new Set([...installedIds, skillId]));
        setSkills(skills.map((s) => (s.id === skillId ? { ...s, is_installed: true } : s)));
        if (selectedSkill?.id === skillId) {
          setSelectedSkill({ ...selectedSkill, is_installed: true });
        }
      }
    } catch (error) {
      console.error('安装失败:', error);
    }
  };

  // 执行技能（B9：POST /api/skills/execute，按 skill_name 调用）
  const handleExecute = async (skill: SkillView) => {
    try {
      const response = await fetch(`${SKILLS_API}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_name: skill.name, input_data: {} }),
      });

      if (response.ok) {
        alert('技能执行成功！');
      }
    } catch (error) {
      console.error('执行失败:', error);
    }
  };

  // 沉淀技能审核（B9：promote / reject）
  const handleSedimentReview = async (name: string, action: 'promote' | 'reject') => {
    try {
      const response = await fetch(`${SEDIMENT_API}/skills/${encodeURIComponent(name)}/${action}`, { method: 'POST' });
      if (response.ok) await loadSediment();
    } catch (error) {
      console.error('沉淀技能审核失败:', error);
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
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* 左侧：分类导航（按能力聚合） */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-sm p-6 sticky top-4">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">能力分类</h2>
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
                    <span>{cat.id}</span>
                    <span className="text-sm text-gray-500">({cat.count})</span>
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
                  <option value="newest">按名称</option>
                </select>
              </div>

              {/* 技能沉淀统计（B9：/api/v1/skill-sediment/stats） */}
              {sedimentStats && (
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">技能沉淀</h3>
                  <div className="space-y-1 text-xs text-gray-600">
                    <div>沉淀事件：{sedimentStats.total_events}</div>
                    <div>沉淀技能：{sedimentStats.sedimented_count}</div>
                    <div>已入库：{sedimentStats.promoted} · 已拒绝：{sedimentStats.rejected}</div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 右侧：技能列表 */}
          <div className="lg:col-span-3">
            {loading ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                <p className="mt-4 text-gray-600">加载中...</p>
              </div>
            ) : visibleSkills.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-lg">
                <p className="text-gray-600">暂无技能</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {visibleSkills.map((skill) => (
                  <div
                    key={skill.id}
                    role="button"
                    tabIndex={0}
                    className="bg-white rounded-lg shadow-sm hover:shadow-md transition cursor-pointer overflow-hidden"
                    onClick={() => setSelectedSkill(skill)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedSkill(skill); }}
                  >
                    {/* 技能卡片头部 */}
                    <div className="bg-gradient-to-r from-blue-500 to-indigo-600 p-4 text-white">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <span className="text-3xl">🧩</span>
                          <div>
                            <h3 className="font-semibold text-lg">{skill.name}</h3>
                            <p className="text-sm text-blue-100">v{skill.version}{skill.author ? ` · ${skill.author}` : ''}</p>
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
                        {skill.description || '暂无描述'}
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
                          <span>{skill.capabilities.length} 项能力</span>
                        </div>
                      </div>

                      {/* 标签 */}
                      <div className="flex flex-wrap gap-2 mb-4">
                        {skill.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs"
                          >
                            {tag}
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
                              handleExecute(skill);
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

            {/* 技能沉淀草稿审核（B9：/api/v1/skill-sediment/skills） */}
            {sedimentDrafts.length > 0 && (
              <div className="mt-8 bg-white rounded-lg shadow-sm p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">待审核的沉淀技能</h2>
                <div className="space-y-3">
                  {sedimentDrafts.map((draft) => {
                    const name = String(draft.name ?? draft.skill_name ?? '');
                    if (!name) return null;
                    return (
                      <div key={name} className="flex items-center justify-between rounded-xl border px-4 py-3">
                        <div>
                          <div className="font-medium text-gray-900">{name}</div>
                          <div className="text-xs text-gray-500">
                            {draft.description ? String(draft.description) : '由执行轨迹自动沉淀'}
                            {typeof draft.usage_count === 'number' ? ` · 使用 ${draft.usage_count} 次` : ''}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSedimentReview(name, 'promote')}
                            className="px-3 py-1 bg-green-500 hover:bg-green-600 text-white rounded text-sm"
                          >
                            确认入库
                          </button>
                          <button
                            onClick={() => handleSedimentReview(name, 'reject')}
                            className="px-3 py-1 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded text-sm"
                          >
                            拒绝
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 技能详情模态框 */}
      {selectedSkill && (
        <div
          role="button"
          tabIndex={0}
          aria-label="Close skill details"
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
          onClick={() => setSelectedSkill(null)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedSkill(null); }}
        >
          {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/click-events-have-key-events */}
          <div
            role="dialog"
            aria-label="Skill details"
            className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 详情头部 */}
            <div className="bg-gradient-to-r from-blue-500 to-indigo-600 p-6 text-white">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <span className="text-5xl">🧩</span>
                  <div>
                    <h2 className="text-2xl font-bold">{selectedSkill.name}</h2>
                    <p className="text-blue-100">v{selectedSkill.version}</p>
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
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">这个技能是干什么的？</h3>
                <p className="text-gray-700 whitespace-pre-wrap">{selectedSkill.description || '暂无描述'}</p>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">能力</h3>
                <div className="flex flex-wrap gap-2">
                  {selectedSkill.capabilities.length ? selectedSkill.capabilities.map((capability) => (
                    <span key={capability} className="bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-sm">{capability}</span>
                  )) : <span className="text-gray-500 text-sm">未标注能力</span>}
                </div>
              </div>

              {/* 统计信息 */}
              <div className="grid grid-cols-3 gap-4 bg-gray-50 p-4 rounded-lg">
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">{selectedSkill.rating.toFixed(1)}</div>
                  <div className="text-sm text-gray-600">评分</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">{selectedSkill.downloads}</div>
                  <div className="text-sm text-gray-600">下载</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-orange-600">{selectedSkill.tags.length}</div>
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
                    onClick={() => handleExecute(selectedSkill)}
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
