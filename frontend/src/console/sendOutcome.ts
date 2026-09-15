/**
 * console 写路径（发消息 / 邀请成员 / 创建智能体）的统一「成败结果」口径。
 *
 * 历史缺陷：这些 handler 声明 `Promise<void>`，但失败时要么静默 `return`、
 * 要么把异常抛给没人接的调用方；调用方一律无条件清空输入框 —— 用户看到
 * 「输入没了，消息没发出去」，且没有任何反馈。
 *
 * 现在改为返回本类型，由调用方按结果决定：ok 才清空输入，否则展示 error。
 */

/** 写操作的结果。`ok: false` 一定带可展示的原因。 */
export type SendOutcome = { ok: true } | { ok: false; error: string };

/**
 * 把任意异常收敛成可展示的失败结果。
 *
 * 返回类型收窄到失败分支（而非整个 `SendOutcome`），这样调用点可以直接读
 * `.error` 而不必先做 narrowing —— 本函数**只**产出失败结果。
 *
 * @param action 中文动作名，用于拼出「发送消息失败：...」这类可读文案
 * @param cause  catch 到的任意值
 */
export function sendFailure(action: string, cause: unknown): { ok: false; error: string } {
  const detail = cause instanceof Error ? cause.message : String(cause ?? "").trim();
  return { ok: false, error: detail ? `${action}失败：${detail}` : `${action}失败` };
}

/**
 * HTTP 状态码 → 用户可读中文。
 *
 * 三个协作写请求助手原本直接抛 `Failed to send collaboration message: ${status}`，
 * 经 sendFailure 拼成「发送消息失败：Failed to send collaboration message: 500」
 * 渲染进 role="alert" —— 中英混排，且把状态码暴露给用户。
 *
 * 状态码本身不再进用户文案：console 当前没有前端错误监控通道消费它，
 * 加一个没人读的 code 字段属于 YAGNI。排障按后端日志的请求时间定位。
 */
export function httpErrorMessage(status: number): string {
  if (status === 400) return "请求内容有误，请检查后重试";
  if (status === 401) return "登录状态已失效，请重新登录";
  if (status === 403) return "没有权限执行该操作";
  if (status === 404) return "目标不存在或已被删除";
  if (status === 409) return "操作冲突，请刷新后重试";
  if (status === 422) return "提交的内容不符合要求";
  if (status === 429) return "操作过于频繁，请稍后再试";
  if (status >= 500) return "服务暂时不可用，请稍后再试";
  return "请求未能完成，请稍后再试";
}
