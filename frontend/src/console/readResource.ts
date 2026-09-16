/**
 * console 读路径的统一「远端资源」口径。
 *
 * 历史缺陷（22 处 / 21 文件，见 .workbuddy/artifacts/2026-09-16_读路径静默降级_归一化清单与分级.md）：
 *
 *     const response = await fetch(url);
 *     if (!response.ok) return;                 // ← 失败静默返回
 *     ...
 *     const total = props.total ?? apiData?.primary.total_items ?? 0;   // ← 失败后渲染 0
 *
 * 失败与「本来没数据」在 UI 上完全同形：用户看到「事件总数 0 / 最近状态 -」，
 * 以为查过了、就是没有。execution 域更严重：兜底是硬编码的业务对象，
 * 直接伪造出「可恢复 / 置信度 92% / 先重试」这类处置指引。
 *
 * 本模块把「失败」与「空」在**类型层**分开 —— 不是靠约定，而是让
 * 失败态在类型上就不可能有 data：
 *
 *     { status: "failed"; data: null } | { status: "ready"; data: T }
 *
 * 于是 `state.data ?? 0` 这类兜底链在 ready 之外的分支上根本写不出来。
 */

import { useCallback, useEffect, useState } from "react";

import { httpErrorMessage } from "./sendOutcome";

/** 读路径的四态。`data` 只在 `ready` 时存在。 */
export type ReadState<T> =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: null; error: null }
  | { status: "failed"; data: null; error: string }
  | { status: "ready"; data: T; error: null };

/**
 * 没有可读资源（例如「还没选中要查看的 run」）。
 *
 * 与 `loading` 分开：把「请求中」和「压根不该请求」混成一个态，
 * 调用方就只能靠 url 是否为空来判断，迟早会写出「永久转圈」的页面。
 */
export const READ_IDLE: ReadState<never> = { status: "idle", data: null, error: null };

export const READ_LOADING: ReadState<never> = { status: "loading", data: null, error: null };

/**
 * 把 catch 到的任意值收敛成**纯原因**文案。
 *
 * 刻意不用 `sendFailure()`：它会拼成「加载发布历史失败：…」，而视图侧
 * `ConsoleReadFailure` 的标题已经写了「加载发布历史失败」—— 复用会得到
 * 「加载发布历史失败：加载发布历史失败：…」的双前缀。
 */
function failureDetail(cause: unknown): string {
  const detail = cause instanceof Error ? cause.message : String(cause ?? "").trim();
  return detail || "网络异常或服务未响应";
}

export type ConsoleResource<T> = ReadState<T> & { reload: () => void };

/**
 * 拉取一个 console 读接口。
 *
 * @param url    请求地址（调用方负责 encode）；传 `null` 表示当前没有可读资源，
 *               此时**不发请求**并停留在 `idle`
 * @param action 中文动作名，用于错误文案标题，如「加载发布历史」
 * @param deps   额外依赖（如 runId）：变化时重新拉取
 */
export function useConsoleResource<T>(
  url: string | null,
  action: string,
  deps: React.DependencyList = [],
): ConsoleResource<T> {
  const [state, setState] = useState<ReadState<T>>(url === null ? READ_IDLE : READ_LOADING);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;

    if (url === null) {
      // 没有可读资源：不发请求，也不假装在加载
      setState(READ_IDLE);
      return () => {
        cancelled = true;
      };
    }

    setState(READ_LOADING);

    const load = async () => {
      try {
        const response = await fetch(url, {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        });
        if (!response.ok) {
          // 关键：进入 failed，而不是静默 return
          if (!cancelled) {
            setState({ status: "failed", data: null, error: httpErrorMessage(response.status) });
          }
          return;
        }
        const payload = (await response.json()) as T;
        if (!cancelled) {
          setState({ status: "ready", data: payload, error: null });
        }
      } catch (cause) {
        if (!cancelled) {
          setState({ status: "failed", data: null, error: failureDetail(cause) });
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, action, nonce, ...deps]);

  return { ...state, reload };
}

/** 「失败 ≠ 空」的判别式：供视图层分流用，避免各处重写 `status === "failed"`。 */
export function readFailure(state: ReadState<unknown>): string | null {
  return state.status === "failed" ? state.error : null;
}
