export interface Source {
  title: string;
  url: string;
  text: string;
  score: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  answered: boolean;
  feedback?: "up" | "down" | null;
}

export interface ChatSummary {
  id: string;
  title: string;
  updatedAt: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:4000";

/** Anonymous per-browser id; the gateway uses it to keep chats private. */
export function getClientId(): string {
  const key = "studypath-client-id";
  try {
    let id = window.localStorage.getItem(key);
    if (!id) {
      id = crypto.randomUUID();
      window.localStorage.setItem(key, id);
    }
    return id;
  } catch {
    return crypto.randomUUID(); // storage blocked: chats just will not persist across reloads
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "x-client-id": getClientId(), ...init?.headers },
  });
  const body: unknown = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message = (body as { error?: string }).error ?? `Request failed (${res.status})`;
    throw new Error(message);
  }
  return body as T;
}

export function sendMessage(message: string, chatId?: string) {
  return request<{ chatId: string; message: ChatMessage }>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message, chatId }),
  });
}

export const listChats = () => request<{ chats: ChatSummary[] }>("/api/chats");

export const getChat = (id: string) =>
  request<{ id: string; title: string; messages: ChatMessage[] }>(`/api/chats/${id}`);

export const sendFeedback = (chatId: string, messageId: string, value: "up" | "down") =>
  request<{ ok: boolean }>("/api/feedback", {
    method: "POST",
    body: JSON.stringify({ chatId, messageId, value }),
  });
