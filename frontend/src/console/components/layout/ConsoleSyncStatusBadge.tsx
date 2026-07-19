import React from "react";

export function ConsoleSyncStatusBadge(props: {
  status: "idle" | "bootstrapping" | "sse" | "polling" | "error";
  lastSyncedAt?: string | null;
  error?: string | null;
  reconnectAttempts?: number;
  onRefresh?: () => void;
  onReconnect?: () => void;
}) {
  const colorClass = {
    idle: "bg-gray-100 text-gray-700",
    bootstrapping: "bg-blue-100 text-blue-700",
    sse: "bg-green-100 text-green-700",
    polling: "bg-yellow-100 text-yellow-700",
    error: "bg-red-100 text-red-700",
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
    <div className="flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2">
      <span className={`rounded-full px-2 py-1 text-xs font-medium ${colorClass}`}>{label}</span>
      <div className="text-xs text-gray-500">
        <div>{statusDescription}</div>
        <div>{props.lastSyncedAt ? `最近同步：${props.lastSyncedAt}` : "尚未同步"}</div>
        {typeof props.reconnectAttempts === "number" ? <div>重连次数：{props.reconnectAttempts}</div> : null}
      </div>
      {props.error ? <div className="max-w-[260px] truncate text-xs text-red-500" title={props.error}>{props.error}</div> : null}
      <div className="flex items-center gap-2">
        <button className="rounded-lg border px-2 py-1 text-xs hover:bg-gray-50" onClick={props.onRefresh}>
          刷新
        </button>
        <button className="rounded-lg border px-2 py-1 text-xs hover:bg-gray-50" onClick={props.onReconnect}>
          重连
        </button>
      </div>
    </div>
  );
}
