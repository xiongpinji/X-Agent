import React from "react";

/**
 * B10 修复：后端没有 /api/v1/templates 路由（backend/app/main.py 未注册任何
 * templates 路由），模板市场相关页面统一标注"后端模板市场未上线"并禁用操作。
 * 页面保留不删除；待后端模板市场上线后，将 TEMPLATE_MARKET_OFFLINE 置为 false
 * 并恢复数据加载逻辑即可。
 */
export const TEMPLATE_MARKET_OFFLINE = true;

export function TemplateMarketOfflineNotice() {
  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
      <div className="font-semibold">后端模板市场未上线</div>
      <p className="mt-1">
        当前后端未提供模板市场接口（无 /api/v1/templates 路由），本页面的浏览、编辑与实例化操作已暂时禁用。
        待后端模板市场上线后自动恢复。
      </p>
    </section>
  );
}
