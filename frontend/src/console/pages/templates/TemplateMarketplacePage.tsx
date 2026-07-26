import React, { useState } from "react";
import { TEMPLATE_MARKET_OFFLINE, TemplateMarketOfflineNotice } from "./TemplateMarketOfflineNotice";

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  status: string;
  tags: string[];
  author: string;
  created_at: string;
  updated_at: string;
  usage_count: number;
  rating: number;
  review_count: number;
}

interface TemplateMarketplacePageProps {
  onSelectTemplate?: (template: WorkflowTemplate) => void;
}

/**
 * 模板市场页（B10）。
 *
 * 后端无 /api/v1/templates 路由（main.py 未注册 templates 路由），
 * 因此页面显式标注"后端模板市场未上线"并禁用全部操作；页面保留不删除。
 * 原实现中的 /api/v1/templates* 请求已移除，待后端的模板市场上线后恢复。
 */
export function TemplateMarketplacePage({ onSelectTemplate: _onSelectTemplate }: TemplateMarketplacePageProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("");

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border bg-white p-6 shadow-sm">
        <h1 className="text-3xl font-bold mb-2">模板市场</h1>
        <p className="text-gray-600">
          发现和使用预构建的工作流模板，加速自动化落地
        </p>
      </section>

      <TemplateMarketOfflineNotice />

      {/* Search and Filters（离线期间禁用） */}
      <section className="space-y-4">
        <div className="flex gap-4">
          <input
            placeholder="搜索模板..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            disabled={TEMPLATE_MARKET_OFFLINE}
            className="flex-1 rounded-lg border border-gray-300 px-4 py-2 disabled:cursor-not-allowed disabled:bg-gray-100"
          />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            disabled={TEMPLATE_MARKET_OFFLINE}
            className="rounded-lg border border-gray-300 px-4 py-2 disabled:cursor-not-allowed disabled:bg-gray-100"
          >
            <option value="">全部分类</option>
          </select>
          <button
            disabled={TEMPLATE_MARKET_OFFLINE}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            切换视图
          </button>
        </div>
      </section>

      {/* Templates（离线空态） */}
      <section>
        <div className="rounded-2xl border border-dashed bg-white py-16 text-center">
          <p className="text-gray-600">模板市场暂未上线，暂无可用模板。</p>
          <button
            disabled={TEMPLATE_MARKET_OFFLINE}
            className="mt-4 rounded-lg bg-blue-600 px-6 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            使用模板
          </button>
        </div>
      </section>
    </div>
  );
}

export default TemplateMarketplacePage;
