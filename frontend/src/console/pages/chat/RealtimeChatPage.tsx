import React, { useMemo, useState } from "react";

export type RealtimeChatPageProps = {
  conversations: ConversationSummary[];
  activeConversationId?: string | null;
  messages: RealtimeMessage[];
  avatars: RoleAvatar[];
  presence: PresenceMap;
  currentSenderId: string;
  onSelectConversation: (conversationId: string) => void;
  onMessageSent?: () => void;
  onOpenAudit?: (messageId?: string) => void;
  onOpenRoom?: (roomId: string) => void;
  onOpenMessageThread?: (messageId: string) => void;
};

export function RealtimeChatPage(props: RealtimeChatPageProps) {
  const activeConversation = useMemo(
    () => props.conversations.find((conversation) => conversation.conversation_id === props.activeConversationId) ?? props.conversations[0] ?? null,
    [props.conversations, props.activeConversationId],
  );
  const threadMessages = useMemo(
    () => props.messages.filter((message) => message.conversation_id === activeConversation?.conversation_id),
    [props.messages, activeConversation?.conversation_id],
  );
  const [localMessages, setLocalMessages] = useState<RealtimeMessage[]>([]);
  const visibleMessages = useMemo(
    () => [...threadMessages, ...localMessages].sort((a, b) => a.created_at.localeCompare(b.created_at)),
    [threadMessages, localMessages],
  );

  const handleSendMessage = async (content: string) => {
    if (!activeConversation) return;
    const created = await postCollaborationMessage({
      roomId: activeConversation.room_id ?? activeConversation.conversation_id,
      senderId: props.currentSenderId,
      senderType: "agent",
      content,
      messageType: "text",
      mentions: [],
      metadata: { conversation_id: activeConversation.conversation_id },
    });
    setLocalMessages((prev) => [...prev, created]);
    props.onMessageSent?.();
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)_300px]">
      <aside className="rounded-2xl border bg-white p-4 shadow-sm">
        <header className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">实时通讯</h2>
            <p className="text-sm text-gray-500">私聊、群聊、会议室统一消息流。</p>
          </div>
          <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onSelectConversation(activeConversation?.conversation_id ?? props.conversations[0]?.conversation_id ?? "")}>返回当前</button>
        </header>
        <div className="mt-4 space-y-2">
          {props.conversations.map((conversation) => (
            <button
              key={conversation.conversation_id}
              className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                activeConversation?.conversation_id === conversation.conversation_id ? "border-blue-500 bg-blue-50" : "hover:bg-gray-50"
              }`}
              onClick={() => props.onSelectConversation(conversation.conversation_id)}
            >
              <div className="font-medium">{conversation.title}</div>
              <div className="mt-1 text-xs text-gray-500">未读 {conversation.unread_count} · 成员 {conversation.participant_ids.length}</div>
            </button>
          ))}
        </div>
      </aside>

      <main className="rounded-2xl border bg-white p-4 shadow-sm">
        {activeConversation ? (
          <>
            <header className="border-b pb-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">{activeConversation.title}</h2>
                  <p className="mt-1 text-sm text-gray-500">最近消息：{activeConversation.last_message_at ?? "-"}</p>
                </div>
                <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenRoom?.(activeConversation.room_id ?? activeConversation.conversation_id)}>
                  打开关联房间
                </button>
              </div>
            </header>
            <section className="mt-4 min-h-[420px]">
              <ChatThreadPanel messages={visibleMessages} avatars={props.avatars} currentUserId={props.currentSenderId} onOpenAudit={props.onOpenAudit} onOpenRoom={props.onOpenRoom} onOpenMessageThread={props.onOpenMessageThread} />
            </section>
            <section className="mt-4">
              <ChatComposer onSend={handleSendMessage} />
            </section>
          </>
        ) : <div className="flex min-h-[420px] items-center justify-center text-sm text-gray-500">暂无对话可显示</div>}
      </main>

      <aside className="space-y-4 rounded-2xl border bg-white p-4 shadow-sm">
        <ChatPresencePanel presence={props.presence} />
        <ChatMemberPanel conversation={activeConversation} avatars={props.avatars} />
        <ChatReferencePanel />
      </aside>
    </div>
  );
}

function ChatThreadPanel({ messages, avatars, currentUserId, onOpenAudit, onOpenRoom, onOpenMessageThread }: { messages: RealtimeMessage[]; avatars: RoleAvatar[]; currentUserId?: string; onOpenAudit?: (messageId?: string) => void; onOpenRoom?: (roomId: string) => void; onOpenMessageThread?: (messageId: string) => void; }) {
  return (
    <div className="space-y-3">
      {messages.length ? messages.map((message) => {
        const avatar = avatars.find((item) => item.avatar_id === message.sender_avatar_id);
        const isMine = currentUserId && (message.sender_id === currentUserId || message.sender_type === "user");
        return (
          <div key={message.message_id} className={`rounded-xl border px-3 py-2 ${isMine ? "bg-blue-50" : "bg-white"}`}>
            <ChatMessageMeta senderName={avatar?.display_name ?? message.sender_name} createdAt={message.created_at} messageType={message.message_type} />
            <div className="mt-2 text-sm text-gray-800">{message.content}</div>
            {message.references?.length ? <div className="mt-2 text-xs text-blue-600">引用：{message.references.join(", ")}</div> : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="rounded-lg border px-2 py-1 text-xs hover:bg-gray-50" onClick={() => onOpenAudit?.(message.message_id)}>查看审计</button>
              <button className="rounded-lg border px-2 py-1 text-xs hover:bg-gray-50" onClick={() => onOpenMessageThread?.(message.message_id)}>查看线程</button>
              {message.room_id ? <button className="rounded-lg border px-2 py-1 text-xs hover:bg-gray-50" onClick={() => onOpenRoom?.(message.room_id ?? "")}>打开房间</button> : null}
            </div>
          </div>
        );
      }) : <div className="rounded-xl border border-dashed p-6 text-center text-sm text-gray-500">这个对话还没有消息</div>}
    </div>
  );
}

function ChatComposer({ onSend }: { onSend: (content: string) => Promise<void>; }) {
  const [value, setValue] = useState("");
  const [sending, setSending] = useState(false);
  return (
    <div className="rounded-2xl border bg-gray-50 p-3">
      <textarea className="min-h-[92px] w-full rounded-xl border bg-white p-3 text-sm" value={value} onChange={(e) => setValue(e.target.value)} placeholder="输入消息，支持 @、引用、任务链接..." />
      <div className="mt-3 flex justify-end gap-2">
        <button className="rounded-lg border px-3 py-2 text-sm">引用</button>
        <button className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50" disabled={sending} onClick={async () => { if (!value.trim()) return; setSending(true); try { await onSend(value); setValue(""); } finally { setSending(false); } }}>
          {sending ? "发送中..." : "发送"}
        </button>
      </div>
    </div>
  );
}

function ChatMessageMeta({ senderName, createdAt, messageType }: { senderName: string; createdAt: string; messageType: string; }) {
  return <div className="flex items-center justify-between text-xs text-gray-500"><span className="font-medium text-gray-700">{senderName}</span><div className="flex items-center gap-2"><span>{messageType}</span><span>{createdAt}</span></div></div>;
}

function ChatPresencePanel({ presence }: { presence: PresenceMap }) {
  return <section><h3 className="font-semibold">在线状态</h3><div className="mt-3 space-y-2">{Object.entries(presence).length ? Object.entries(presence).map(([agentId, info]) => <div key={agentId} className="rounded-xl border px-3 py-2 text-sm"><div className="font-medium">{agentId}</div><div className="text-xs text-gray-500">{info.status ?? "unknown"}</div></div>) : <div className="text-sm text-gray-500">暂无在线数据</div>}</div></section>;
}

function ChatMemberPanel({ conversation, avatars }: { conversation: ConversationSummary | null; avatars: RoleAvatar[]; }) {
  return <section><h3 className="font-semibold">成员</h3><div className="mt-3 space-y-2">{conversation?.participant_ids?.length ? conversation.participant_ids.map((participantId, index) => <div key={participantId} className="flex items-center gap-3 rounded-xl border px-3 py-2"><div className="h-10 w-10 rounded-full bg-gray-200" /><div><div className="text-sm font-medium">{participantId}</div><div className="text-xs text-gray-500">{avatars[index]?.display_name ?? "角色成员"}</div></div></div>) : <div className="text-sm text-gray-500">暂无成员</div>}</div></section>;
}

function ChatReferencePanel() {
  return <section><h3 className="font-semibold">引用</h3><div className="mt-3 rounded-xl border p-3 text-sm text-gray-500">暂未接入引用面板</div></section>;
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
