/**
 * 读路径的三种可见态：加载中 / 失败 / 空。
 *
 * 三者必须**互斥且各自可见**。历史缺陷是「失败」既没有独立渲染分支，
 * 又在兜底值上与「空」同形 —— 用户无法区分「没查到」和「没数据」。
 *
 * 复用设计系统原语（`ui/Alert` / `ui/EmptyState`），不再往页面里手写
 * 第三套状态样式；失败态带 `role="alert"`，空态带明确文案，二者在
 * DOM 上就是可判别的。
 */

import React from "react";

import { Alert } from "@/components/ui/Alert";
import { EmptyState } from "@/components/ui/EmptyState";

export type ConsoleReadLoadingProps = {
  /** 中文动作名，如「加载发布历史」 */
  action: string;
};

/** 加载中。`role="status"` 让读屏能播报，不打断当前焦点。 */
export function ConsoleReadLoading({ action }: ConsoleReadLoadingProps) {
  return (
    <p role="status" className="text-sm text-gray-500">
      {action}中…
    </p>
  );
}

export type ConsoleReadFailureProps = {
  /** 中文动作名，如「加载发布历史」 */
  action: string;
  /** **纯原因**文案（不含 action 前缀），由 useConsoleResource 产出 */
  message: string;
  onRetry?: () => void;
};

/** 失败态。标题写明「什么动作失败了」，正文是原因，附重试入口。 */
export function ConsoleReadFailure({ action, message, onRetry }: ConsoleReadFailureProps) {
  return (
    <Alert variant="error" title={`${action}失败`}>
      <p>{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md border border-[var(--divider)] px-3 py-1.5 text-sm hover:bg-[var(--surface-raised)]"
        >
          重试
        </button>
      )}
    </Alert>
  );
}

export type ConsoleReadEmptyProps = {
  title?: string;
  description?: string;
};

/** 空态。只有**确实查到了、但结果为空**时才应渲染这个。 */
export function ConsoleReadEmpty({ title = "暂无数据", description }: ConsoleReadEmptyProps) {
  return <EmptyState title={title} description={description} />;
}
