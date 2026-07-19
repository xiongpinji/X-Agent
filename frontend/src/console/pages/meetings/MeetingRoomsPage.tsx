import React, { useMemo, useState } from "react";

export type MeetingRoomsPageProps = {
  rooms: MeetingRoomSummary[];
  activeRoomId?: string | null;
  messages: RealtimeMessage[];
  avatars: RoleAvatar[];
  currentSenderId: string;
  onSelectRoom: (roomId: string) => void;
  onRoomMessageSent?: () => void;
  onInviteMemberSent?: () => void;
};

export function MeetingRoomsPage(props: MeetingRoomsPageProps) {
  const activeRoom = useMemo(
    () => props.rooms.find((room) => room.room_id === props.activeRoomId) ?? props.rooms[0] ?? null,
    [props.rooms, props.activeRoomId],
  );
  const roomMessages = useMemo(
    () => props.messages.filter((msg) => msg.room_id === activeRoom?.room_id),
    [props.messages, activeRoom?.room_id],
  );
  const [localMessages, setLocalMessages] = useState<RealtimeMessage[]>([]);
  const visibleMessages = useMemo(
    () => [...roomMessages, ...localMessages].sort((a, b) => a.created_at.localeCompare(b.created_at)),
    [roomMessages, localMessages],
  );

  const handleSendMessage = async (payload: SendMessagePayload) => {
    if (!payload.roomId) return;
    const created = await postCollaborationMessage({
      roomId: payload.roomId,
      senderId: props.currentSenderId,
      senderType: "agent",
      content: payload.content,
      messageType: "text",
      mentions: [],
      metadata: {},
    });
    setLocalMessages((prev) => [...prev, created]);
    props.onRoomMessageSent?.();
  };

  const handleInviteAgent = async (agentId: string) => {
    if (!activeRoom) return;
    await addCollaborationMember({ roomId: activeRoom.room_id, memberId: agentId });
    props.onInviteMemberSent?.();
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)_320px]">
      <aside className="rounded-2xl border bg-white p-4 shadow-sm">
        <header className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">会议室</h2>
            <p className="text-sm text-gray-500">选择一个房间进入协作。</p>
          </div>
          <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onSelectRoom(activeRoom?.room_id ?? props.rooms[0]?.room_id ?? "")}>返回当前</button>
        </header>
        <div className="mt-4 space-y-2">
          {props.rooms.map((room) => (
            <button
              key={room.room_id}
              className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                activeRoom?.room_id === room.room_id ? "border-blue-500 bg-blue-50" : "hover:bg-gray-50"
              }`}
              onClick={() => props.onSelectRoom(room.room_id)}
            >
              <div className="font-medium">{room.name}</div>
              <div className="mt-1 text-xs text-gray-500">{room.topic}</div>
              <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
                <span>{room.member_count ?? room.member_agent_ids.length} 成员</span>
                <span>{room.status}</span>
              </div>
            </button>
          ))}
        </div>
      </aside>

      <main className="rounded-2xl border bg-white p-4 shadow-sm">
        {activeRoom ? (
          <>
            <header className="border-b pb-4">
              <h2 className="text-lg font-semibold">{activeRoom.name}</h2>
              <p className="mt-1 text-sm text-gray-500">{activeRoom.topic}</p>
            </header>
            <section className="mt-4">
              <MeetingRoomMessageStream messages={visibleMessages} avatars={props.avatars} />
            </section>
            <section className="mt-4">
              <MeetingRoomActionBar roomId={activeRoom.room_id} onSendMessage={handleSendMessage} />
            </section>
          </>
        ) : (
          <div className="flex min-h-[360px] items-center justify-center text-sm text-gray-500">暂无会议室可显示</div>
        )}
      </main>

      <aside className="space-y-4 rounded-2xl border bg-white p-4 shadow-sm">
        {activeRoom ? (
          <>
            <MeetingRoomMemberPanel room={activeRoom} avatars={props.avatars} onInviteAgent={handleInviteAgent} />
            <MeetingRoomTopicPanel room={activeRoom} />
            <MeetingRoomTaskBoard />
            <MeetingRoomMemoPanel />
            <MeetingRoomValidationPanel />
          </>
        ) : null}
      </aside>
    </div>
  );
}

function MeetingRoomMessageStream({ messages, avatars }: { messages: RealtimeMessage[]; avatars: RoleAvatar[] }) {
  return (
    <div className="space-y-3">
      {messages.length ? messages.map((msg) => {
        const avatar = avatars.find((a) => a.avatar_id === msg.sender_avatar_id);
        return (
          <div key={msg.message_id} className="rounded-xl border px-3 py-2">
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>{avatar?.display_name ?? msg.sender_name}</span>
              <span>{msg.created_at}</span>
            </div>
            <div className="mt-2 text-sm text-gray-800">{msg.content}</div>
            {msg.references?.length ? <div className="mt-2 text-xs text-blue-600">引用：{msg.references.join(", ")}</div> : null}
          </div>
        );
      }) : <div className="rounded-xl border border-dashed p-6 text-center text-sm text-gray-500">还没有消息，开始讨论吧。</div>}
    </div>
  );
}

function MeetingRoomActionBar({ roomId, onSendMessage }: { roomId: string; onSendMessage: (payload: SendMessagePayload) => Promise<void>; }) {
  const [value, setValue] = useState("");
  const [sending, setSending] = useState(false);
  return (
    <div className="rounded-2xl border bg-gray-50 p-3">
      <textarea className="min-h-[88px] w-full rounded-xl border bg-white p-3 text-sm" value={value} onChange={(e) => setValue(e.target.value)} placeholder="输入会议消息，支持 @ 某个智能体、引用任务、发起确认..." />
      <div className="mt-3 flex justify-end gap-2">
        <button className="rounded-lg border px-3 py-2 text-sm">引用</button>
        <button className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50" disabled={sending} onClick={async () => { if (!value.trim()) return; setSending(true); try { await onSendMessage({ roomId, content: value, references: [] }); setValue(""); } finally { setSending(false); } }}>
          {sending ? "发送中..." : "发送"}
        </button>
      </div>
    </div>
  );
}

function MeetingRoomMemberPanel({ room, avatars, onInviteAgent }: { room: MeetingRoomSummary; avatars: RoleAvatar[]; onInviteAgent?: (agentId: string) => void; }) {
  const [inviteId, setInviteId] = useState("");
  return (
    <section>
      <h3 className="font-semibold">成员</h3>
      <div className="mt-3 space-y-2">
        {room.member_agent_ids.map((agentId) => {
          const avatar = avatars.find((a) => a.avatar_id === agentId || a.role_name === agentId);
          return (
            <div key={agentId} className="flex items-center gap-3 rounded-xl border px-3 py-2">
              <div className="h-10 w-10 rounded-full bg-gray-200" />
              <div>
                <div className="text-sm font-medium">{avatar?.display_name ?? agentId}</div>
                <div className="text-xs text-gray-500">在线</div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 rounded-xl border p-3">
        <div className="text-xs text-gray-500">邀请成员</div>
        <div className="mt-2 flex gap-2">
          <input className="min-w-0 flex-1 rounded-lg border px-3 py-2 text-sm" placeholder="输入 member_id" value={inviteId} onChange={(e) => setInviteId(e.target.value)} />
          <button className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white" onClick={() => { if (!inviteId.trim()) return; onInviteAgent?.(inviteId.trim()); setInviteId(""); }}>邀请</button>
        </div>
      </div>
    </section>
  );
}

function MeetingRoomTopicPanel({ room }: { room: MeetingRoomSummary }) {
  return <section><h3 className="font-semibold">议题</h3><div className="mt-3 rounded-xl border p-3 text-sm text-gray-600">{room.topic || "暂无议题"}</div></section>;
}

function MeetingRoomTaskBoard() {
  return <section><h3 className="font-semibold">任务</h3><div className="mt-3 rounded-xl border p-3 text-sm text-gray-500">暂未接入任务看板</div></section>;
}

function MeetingRoomMemoPanel() {
  return <section><h3 className="font-semibold">纪要</h3><div className="mt-3 rounded-xl border p-3 text-sm text-gray-500">暂无纪要</div></section>;
}

function MeetingRoomValidationPanel() {
  return <section><h3 className="font-semibold">验证</h3><div className="mt-3 rounded-xl border p-3 text-sm text-gray-500">暂未接入验证结果</div></section>;
}

async function postCollaborationMessage(params: { roomId: string; senderId: string; senderType?: string; content: string; messageType?: string; mentions?: string[]; metadata?: Record<string, unknown>; }): Promise<RealtimeMessage> {
  const response = await fetch(`/api/v1/collaboration/rooms/${params.roomId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sender_id: params.senderId, sender_type: params.senderType ?? "agent", content: params.content, message_type: params.messageType ?? "text", mentions: params.mentions ?? [], metadata: params.metadata ?? {} }),
  });
  if (!response.ok) throw new Error(`Failed to send collaboration message: ${response.status}`);
  return response.json();
}

async function addCollaborationMember(params: { roomId: string; memberId: string; }): Promise<Record<string, unknown>> {
  const response = await fetch(`/api/v1/collaboration/rooms/${params.roomId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ member_id: params.memberId }),
  });
  if (!response.ok) throw new Error(`Failed to add collaboration member: ${response.status}`);
  return response.json();
}
