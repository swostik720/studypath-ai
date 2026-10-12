"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getChat,
  listChats,
  sendFeedback,
  sendMessage,
  type ChatMessage,
  type ChatSummary,
} from "@/lib/api";
import { SourceList } from "./SourceList";

const SUGGESTIONS = [
  "What is a blocked account?",
  "How early should I apply via uni-assist?",
  "What are the application periods for the Data Engineering and Analytics master's at TUM?",
];

export default function Chat() {
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [chatId, setChatId] = useState<string | undefined>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshChats = useCallback(async () => {
    try {
      setChats((await listChats()).chats);
    } catch {
      /* history is optional; the chat itself reports errors */
    }
  }, []);

  useEffect(() => {
    // Load history once on mount; setState happens in the promise callback, not in the effect body.
    let alive = true;
    listChats()
      .then((r) => alive && setChats(r.chats))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function openChat(id: string) {
    setError(null);
    setSidebarOpen(false);
    try {
      const chat = await getChat(id);
      setChatId(chat.id);
      setMessages(chat.messages);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function newChat() {
    setChatId(undefined);
    setMessages([]);
    setError(null);
    setSidebarOpen(false);
  }

  async function submit(text: string) {
    const question = text.trim();
    if (question.length < 3 || loading) return;
    setInput("");
    setError(null);
    setLoading(true);
    setMessages((m) => [
      ...m,
      { id: `local-${Date.now()}`, role: "user", content: question, sources: [], answered: true },
    ]);
    try {
      const res = await sendMessage(question, chatId);
      setChatId(res.chatId);
      setMessages((m) => [...m, res.message]);
      void refreshChats();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function rate(message: ChatMessage, value: "up" | "down") {
    if (!chatId) return;
    setMessages((all) => all.map((m) => (m.id === message.id ? { ...m, feedback: value } : m)));
    try {
      await sendFeedback(chatId, message.id, value);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="flex h-dvh bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100">
      <aside
        className={`${sidebarOpen ? "flex" : "hidden"} absolute inset-y-0 left-0 z-10 w-72 flex-col border-r border-slate-200 bg-slate-50 p-3 md:static md:flex dark:border-slate-700 dark:bg-slate-950`}
      >
        <button
          onClick={newChat}
          className="mb-3 rounded-lg bg-blue-700 px-3 py-2 text-sm font-medium text-white hover:bg-blue-800"
        >
          + New chat
        </button>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">History</h2>
        <ul className="flex-1 space-y-1 overflow-y-auto">
          {chats.length === 0 && <li className="text-sm text-slate-500">No chats yet.</li>}
          {chats.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => void openChat(c.id)}
                className={`w-full truncate rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-200 dark:hover:bg-slate-800 ${c.id === chatId ? "bg-slate-200 dark:bg-slate-800" : ""}`}
              >
                {c.title}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
          <button
            className="rounded-md border border-slate-300 px-2 py-1 text-sm md:hidden dark:border-slate-600"
            aria-label="Toggle chat history"
            onClick={() => setSidebarOpen((o) => !o)}
          >
            ☰
          </button>
          <div>
            <h1 className="text-lg font-semibold">StudyPath AI</h1>
            <p className="text-xs text-slate-500">
              Answers come only from a small set of official documents, with sources. Not legal advice.
            </p>
          </div>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-6">
          {messages.length === 0 && (
            <div className="mx-auto max-w-xl text-center">
              <p className="mb-4 text-slate-600 dark:text-slate-300">Ask a question about studying in Germany:</p>
              <div className="flex flex-col gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => void submit(s)}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[90%] rounded-2xl px-4 py-3 md:max-w-2xl ${
                  m.role === "user"
                    ? "bg-blue-700 text-white"
                    : "border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800"
                }`}
              >
                <p className="whitespace-pre-wrap">{m.content}</p>
                {m.role === "assistant" && (
                  <>
                    {!m.answered && (
                      <p className="mt-2 text-xs font-medium text-amber-700 dark:text-amber-400">
                        Not found in my documents - no sources shown.
                      </p>
                    )}
                    <SourceList sources={m.sources} />
                    <div className="mt-3 flex gap-2" role="group" aria-label="Rate this answer">
                      {(["up", "down"] as const).map((v) => (
                        <button
                          key={v}
                          onClick={() => void rate(m, v)}
                          aria-pressed={m.feedback === v}
                          aria-label={v === "up" ? "Helpful answer" : "Unhelpful answer"}
                          className={`rounded-md border px-2 py-1 text-sm ${
                            m.feedback === v
                              ? "border-blue-700 bg-blue-100 dark:bg-blue-900"
                              : "border-slate-300 hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-700"
                          }`}
                        >
                          {v === "up" ? "👍" : "👎"}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start" role="status" aria-live="polite">
              <div className="animate-pulse rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-slate-700">
                Searching documents and writing an answer...
              </div>
            </div>
          )}
          {error && (
            <p
              role="alert"
              className="mx-auto max-w-xl rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200"
            >
              {error}
            </p>
          )}
          <div ref={bottomRef} />
        </div>

        <form
          className="flex gap-2 border-t border-slate-200 p-3 dark:border-slate-700"
          onSubmit={(e) => {
            e.preventDefault();
            void submit(input);
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={1000}
            placeholder="e.g. What is a blocked account?"
            aria-label="Your question"
            className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-blue-700 dark:border-slate-600 dark:bg-slate-800"
          />
          <button
            type="submit"
            disabled={loading || input.trim().length < 3}
            className="rounded-lg bg-blue-700 px-4 py-2 font-medium text-white hover:bg-blue-800 disabled:opacity-50"
          >
            Ask
          </button>
        </form>
      </main>
    </div>
  );
}
