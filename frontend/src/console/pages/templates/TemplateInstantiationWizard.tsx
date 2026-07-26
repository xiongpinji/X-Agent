import React from "react";
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
  min_value?: number;
  max_value?: number;
  min_length?: number;
  max_length?: number;
}

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  parameters: TemplateParameter[];
  nodes: unknown[];
  edges: unknown[];
  tags: string[];
  author: string;
  example_inputs?: Record<string, unknown>;
}

interface TemplateInstantiationWizardProps {
  template: WorkflowTemplate;
  onComplete?: (workflowId: string) => void;
  onCancel?: () => void;
}

/**
 * 模板实例化向导（B10）。
 *
 * 后端无 /api/v1/templates 路由，实例化接口不可用：
 * 页面显式标注"后端模板市场未上线"，参数填写与实例化操作全部禁用。
 * 页面保留不删除；后端的模板市场上线后恢复实例化流程。
 */
export function TemplateInstantiationWizard({
  template,
  onComplete: _onComplete,
  onCancel,
}: TemplateInstantiationWizardProps) {
  return (
    <div className="space-y-6">
      <TemplateMarketOfflineNotice />

      <section className="rounded-2xl border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">实例化模板：{template.name}</h2>
        <p className="mt-1 text-sm text-gray-500">{template.description}</p>

        <div className="mt-6 space-y-4 opacity-60">
          {(template.parameters ?? []).map((param) => (
            <div key={param.name}>
              <label htmlFor={`param-${param.name}`} className="mb-1 block text-sm font-medium">
                {param.name}
                {param.required ? <span className="ml-1 text-red-500">*</span> : null}
              </label>
              <input
                id={`param-${param.name}`}
                placeholder={param.placeholder ?? param.description}
                disabled={TEMPLATE_MARKET_OFFLINE}
                className="w-full rounded-lg border border-gray-300 px-4 py-2 disabled:cursor-not-allowed disabled:bg-gray-100"
              />
              {param.help_text ? <p className="mt-1 text-xs text-gray-400">{param.help_text}</p> : null}
            </div>
          ))}
          {(template.parameters ?? []).length === 0 ? (
            <p className="text-sm text-gray-500">该模板没有可配置参数。</p>
          ) : null}
        </div>
      </section>

      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
        >
          取消
        </button>
        <button
          disabled={TEMPLATE_MARKET_OFFLINE}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          实例化（未上线）
        </button>
      </div>
    </div>
  );
}

export default TemplateInstantiationWizard;
