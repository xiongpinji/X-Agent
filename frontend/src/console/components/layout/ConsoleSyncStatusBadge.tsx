import React from "react";

export function ConsoleSyncStatusBadge(props: {
  status: "idle" | "bootstrapping" | "sse" | "polling" | "error";
  lastSyncedAt?: string | null;
  error?: string | null;
  reconnectAttempts?: number;
  onRefresh?: () => void;
  onReconnect?: () => void;
}) {
  const badgeClass = {
    idle: "badge-muted",
    bootstrapping: "badge-warning",
    sse: "badge-success",
    polling: "badge-warning",
    error: "badge-danger",
  }[props.status];

  const label = {
    idle: "空闲",
    bootstrapping: "启动中",
    sse: "实时连接",
    polling: "轮询兜底",
    error: "同步异常",
  }[props.status];

  const statusDescription = {
    idle: "尚未建立同步连接",
    bootstrapping: "正在加载控制台快照",
    sse: "SSE 实时连接正常",
    polling: "正在使用轮询兜底同步",
    error: "同步失败，已进入降级状态",
  }[props.status];

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className={`badge-status ${badgeClass}`}>{label}</span>
      <div className="text-xs text-gray-500">
        <div>{statusDescription}</div>
        <div>{props.lastSyncedAt ? `最近同步：${props.lastSyncedAt}` : "尚未同步"}</div>
        {typeof props.reconnectAttempts === "number" ? <div>重连次数：{props.reconnectAttempts}</div> : null}
      </div>
      {props.error ? <div className="max-w-[260px] truncate text-xs text-red-500" title={props.error}>{props.error}</div> : null}
      <div className="flex items-center gap-2">
        <button className="border px-2 py-1 text-xs hover:bg-gray-50" onClick={props.onRefresh}>
          刷新
        </button>
        <button className="border px-2 py-1 text-xs hover:bg-gray-50" onClick={props.onReconnect}>
          重连
        </button>
      </div>
    </div>
  );
}
