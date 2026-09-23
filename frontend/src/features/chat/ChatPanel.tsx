"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { ApiError } from "@/lib/api-error";
import { streamChat } from "@/lib/chat-stream";
import type { ChatSource } from "@/lib/types";

interface Turn {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
}

export function ChatPanel() {
  const t = useTranslations("chat");
  const { activeWorkspace } = useWorkspace();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const workspaceId = activeWorkspace?.id ?? null;
  const [conversationId, setConversationId] = useState<number | null>(null);

  function updateLast(update: (turn: Turn) => Turn) {
    setTurns((current) =>
      current.map((turn, index) => (index === current.length - 1 ? update(turn) : turn)),
    );
  }

  function dropEmptyAssistant() {
    setTurns((current) => {
      const last = current[current.length - 1];
      if (last && last.role === "assistant" && last.content === "") {
        return current.slice(0, -1);
      }
      return current;
    });
  }

  async function send() {
    if (!workspaceId || !message.trim() || sending) return;
    const question = message.trim();
    const resumeConversationId = conversationId;
    setMessage("");
    setError(null);
    setSending(true);
    setSearching(true);
    setTurns((current) => [
      ...current,
      { role: "user", content: question },
      { role: "assistant", content: "" },
    ]);

    try {
      await streamChat(
        workspaceId,
        question,
        {
          onSources: (payload) => {
            setSearching(false);
            if (payload.conversation_id) setConversationId(payload.conversation_id);
            updateLast((turn) => ({ ...turn, sources: payload.sources }));
          },
          onToken: (text) =>
            updateLast((turn) => ({ ...turn, content: turn.content + text })),
          onError: (payload) =>
            setError(new ApiError(0, { code: payload.code, message: payload.message })),
        },
        resumeConversationId,
      );
    } catch (err) {
      setError(err);
    } finally {
      setSending(false);
      setSearching(false);
      dropEmptyAssistant();
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>
      <ErrorMessage error={error} />

      {searching && <p className="text-sm text-slate-500">{t("searching")}</p>}

      <div className="flex min-h-48 flex-col gap-3 rounded border border-slate-200 bg-white p-4">
        {turns.length === 0 ? (
          <p className="text-sm text-slate-500">{t("empty")}</p>
        ) : (
          turns.map((turn, index) => (
            <div
              key={index}
              className={`rounded p-2 text-sm ${
                turn.role === "user" ? "bg-slate-100" : "bg-emerald-50"
              }`}
            >
              <p className="whitespace-pre-wrap">{turn.content}</p>
              {turn.sources && turn.sources.length > 0 && (
                <p className="mt-1 text-xs text-slate-500">
                  {t("sources")}:{" "}
                  {turn.sources.map((source) => source.filename).join(", ")}
                </p>
              )}
            </div>
          ))
        )}
      </div>

      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-slate-300 px-2 py-1"
          placeholder={t("placeholder")}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void send();
          }}
        />
        <button
          type="button"
          onClick={send}
          disabled={sending || !message.trim()}
          className="rounded bg-slate-900 px-4 py-1 text-white disabled:opacity-50"
        >
          {sending ? t("sending") : t("send")}
        </button>
      </div>
    </section>
  );
}
