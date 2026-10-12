import { randomUUID } from "node:crypto";
import mongoose from "mongoose";
import { MongoMemoryServer } from "mongodb-memory-server";
import request from "supertest";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { createApp } from "../src/app.js";
import { loadConfig } from "../src/config.js";
import { Chat } from "../src/models.js";
import { RagUnavailableError, type RagClient, type RagResponse } from "../src/ragClient.js";

class FakeRag implements RagClient {
  fail = false;
  calls: string[] = [];
  async ask(question: string): Promise<RagResponse> {
    this.calls.push(question);
    if (this.fail) throw new RagUnavailableError("down");
    return {
      answer: "A blocked account proves your finances [1].",
      answered: true,
      sources: [{ title: "Sperrkonto", url: "https://example.org/s", text: "chunk", score: 0.7 }],
    };
  }
}

let mongo: MongoMemoryServer;
const rag = new FakeRag();
const config = { ...loadConfig({}), rateLimitPerMinute: 1000 };
const app = createApp(config, rag);
const client = randomUUID();

beforeAll(async () => {
  mongo = await MongoMemoryServer.create();
  await mongoose.connect(mongo.getUri());
});
afterAll(async () => {
  await mongoose.disconnect();
  await mongo.stop();
});
beforeEach(async () => {
  await Chat.deleteMany({});
  rag.fail = false;
  rag.calls = [];
});

const post = (path: string, body: unknown, id: string | undefined = client) => {
  const r = request(app).post(path);
  return (id ? r.set("x-client-id", id) : r).send(body as object);
};

describe("POST /api/chat", () => {
  it("creates a chat, stores both messages and returns the answer with sources", async () => {
    const res = await post("/api/chat", { message: "What is a blocked account?" });
    expect(res.status).toBe(201);
    expect(res.body.message.content).toContain("blocked account");
    expect(res.body.message.sources[0].url).toBe("https://example.org/s");
    const saved = await Chat.findById(res.body.chatId);
    expect(saved?.messages.map((m) => m.role)).toEqual(["user", "assistant"]);
  });

  it("appends to an existing chat", async () => {
    const first = await post("/api/chat", { message: "What is a blocked account?" });
    const second = await post("/api/chat", { message: "How do I close it?", chatId: first.body.chatId });
    expect(second.status).toBe(200);
    expect((await Chat.findById(first.body.chatId))?.messages).toHaveLength(4);
  });

  it.each([{}, { message: "" }, { message: "ab" }, { message: "x".repeat(1001) }, { message: 5 }])(
    "rejects invalid body %j with 400",
    async (body) => {
      const res = await post("/api/chat", body);
      expect(res.status).toBe(400);
      expect(res.body.error).toBeDefined();
    },
  );

  it("requires a UUID x-client-id header", async () => {
    expect((await post("/api/chat", { message: "hello there" }, "")).status).toBe(400);
    expect((await post("/api/chat", { message: "hello there" }, "not-a-uuid")).status).toBe(400);
  });

  it("returns 502 and stores nothing when the RAG service is down", async () => {
    rag.fail = true;
    const res = await post("/api/chat", { message: "What is a blocked account?" });
    expect(res.status).toBe(502);
    expect(await Chat.countDocuments()).toBe(0);
  });

  it("rejects malformed JSON with 400", async () => {
    const res = await request(app)
      .post("/api/chat")
      .set("x-client-id", client)
      .set("Content-Type", "application/json")
      .send("{bad json");
    expect(res.status).toBe(400);
  });
});

describe("GET /api/chats", () => {
  it("returns a chat only to its owner", async () => {
    const created = await post("/api/chat", { message: "What is a blocked account?" });
    const mine = await request(app).get(`/api/chats/${created.body.chatId}`).set("x-client-id", client);
    expect(mine.status).toBe(200);
    expect(mine.body.messages).toHaveLength(2);
    const other = await request(app).get(`/api/chats/${created.body.chatId}`).set("x-client-id", randomUUID());
    expect(other.status).toBe(404);
  });

  it("lists my chats and rejects malformed ids", async () => {
    await post("/api/chat", { message: "What is a blocked account?" });
    const list = await request(app).get("/api/chats").set("x-client-id", client);
    expect(list.body.chats).toHaveLength(1);
    expect((await request(app).get("/api/chats/xyz").set("x-client-id", client)).status).toBe(400);
  });
});

describe("POST /api/feedback", () => {
  it("stores thumbs up/down on an assistant message", async () => {
    const created = await post("/api/chat", { message: "What is a blocked account?" });
    const res = await post("/api/feedback", {
      chatId: created.body.chatId,
      messageId: created.body.message.id,
      value: "down",
      comment: "too short",
    });
    expect(res.status).toBe(201);
    const chat = await request(app).get(`/api/chats/${created.body.chatId}`).set("x-client-id", client);
    expect(chat.body.messages[1].feedback).toBe("down");
  });

  it("validates input and unknown messages", async () => {
    const created = await post("/api/chat", { message: "What is a blocked account?" });
    expect((await post("/api/feedback", { chatId: created.body.chatId })).status).toBe(400);
    const bad = await post("/api/feedback", {
      chatId: created.body.chatId,
      messageId: new mongoose.Types.ObjectId().toString(),
      value: "up",
    });
    expect(bad.status).toBe(404);
  });
});

describe("misc", () => {
  it("serves /health and JSON 404s", async () => {
    expect((await request(app).get("/health")).body.status).toBe("ok");
    const res = await request(app).get("/nope");
    expect(res.status).toBe(404);
    expect(res.body.error).toBe("Route not found");
  });

  it("rate limits /api after the configured number of requests", async () => {
    const limited = createApp({ ...config, rateLimitPerMinute: 2 }, rag);
    const get = () => request(limited).get("/api/chats").set("x-client-id", client);
    expect((await get()).status).toBe(200);
    expect((await get()).status).toBe(200);
    expect((await get()).status).toBe(429);
  });
});
