import React, { useState } from "react";
import { TEMPLATE_MARKET_OFFLINE, TemplateMarketOfflineNotice } from "./TemplateMarketOfflineNotice";

interface TemplateParameter {
  name: string;
  type: string;
  description: string;
  default?: unknown;
  required: boolean;
  enum_values?: unknown[];
  placeholder?: string;
  help_text?: string;
}

interface TemplateNode {
  id: string;
  type: string;
  name: string;
  description: string;
  config: Record<string, unknown>;
  position: { x: number; y: number };
}

interface TemplateEdge {
  source: string;
  target: string;
  condition?: string;
  label?: string;
}

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  status: string;
  parameters: TemplateParameter[];
  nodes: TemplateNode[];
  edges: TemplateEdge[];
  tags: string[];
  author: string;
  created_at: string;
  updated_at: string;
  usage_count: number;
  rating: number;
}

interface TemplateEditorProps {
  templateId?: string;
  onSave?: (template: WorkflowTemplate) => void;
  onCancel?: () => void;
}

/**
 * 模板编辑器（B10）。
 *
 * 后端无 /api/v1/templates 路由，模板加载与保存不可用：
 * 页面显式标注"后端模板市场未上线"，表单与保存操作全部禁用。
 * 页面保留不删除；后端的模板市场上线后恢复 loadTemplate / handleSave。
 */
export function TemplateEditor({ templateId: _templateId, onSave: _onSave, onCancel }: TemplateEditorProps) {
  const [template, setTemplate] = useState<Partial<WorkflowTemplate>>({
    name: "",
    description: "",
    category: "custom",
    version: "1.0.0",
    status: "draft",
    parameters: [],
    nodes: [],
    edges: [],
    tags: [],
  });

  return (
    <div className="space-y-6">
      <TemplateMarketOfflineNotice />

      <section className="rounded-2xl border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">模板编辑器</h2>
        <p className="mt-1 text-sm text-gray-500">后端模板市场未上线，编辑功能暂不可用。</p>

        <div className="mt-6 space-y-4 opacity-60">
          <div>
            <label htmlFor="template-name" className="mb-1 block text-sm font-medium">模板名称</label>
            <input
              id="template-name"
              value={template.name || ""}
              onChange={(e) => setTemplate({ ...template, name: e.target.value })}
              placeholder="输入模板名称"
              disabled={TEMPLATE_MARKET_OFFLINE}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 disabled:cursor-not-allowed disabled:bg-gray-100"
            />
          </div>

          <div>
            <label htmlFor="template-description" className="mb-1 block text-sm font-medium">描述</label>
            <textarea
              id="template-description"
              value={template.description || ""}
              onChange={(e) => setTemplate({ ...template, description: e.target.value })}
              placeholder="输入模板描述"
              rows={4}
              disabled={TEMPLATE_MARKET_OFFLINE}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 disabled:cursor-not-allowed disabled:bg-gray-100"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="template-category" className="mb-1 block text-sm font-medium">分类</label>
              <select
                id="template-category"
                value={template.category || "custom"}
                onChange={(e) => setTemplate({ ...template, category: e.target.value })}
                disabled={TEMPLATE_MARKET_OFFLINE}
                className="w-full rounded-lg border border-gray-300 px-4 py-2 disabled:cursor-not-allowed disabled:bg-gray-100"
              >
                <option value="data_processing">数据处理</option>
                <option value="web_scraping">网页采集</option>
                <option value="code_review">代码审查</option>
                <option value="documentation">文档生成</option>
                <option value="custom">自定义</option>
              </select>
            </div>

            <div>
              <label htmlFor="template-version" className="mb-1 block text-sm font-medium">版本</label>
              <input
                id="template-version"
                value={template.version || "1.0.0"}
                onChange={(e) => setTemplate({ ...template, version: e.target.value })}
                placeholder="1.0.0"
                disabled={TEMPLATE_MARKET_OFFLINE}
                className="w-full rounded-lg border border-gray-300 px-4 py-2 disabled:cursor-not-allowed disabled:bg-gray-100"
              />
            </div>
          </div>
        </div>
      </section>

      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
        >
          返回
        </button>
        <button
          disabled={TEMPLATE_MARKET_OFFLINE}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          保存模板（未上线）
        </button>
      </div>
    </div>
  );
}

export default TemplateEditor;
