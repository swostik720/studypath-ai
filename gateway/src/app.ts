import cors from "cors";
import express, { type ErrorRequestHandler, type Express } from "express";
import rateLimit from "express-rate-limit";
import helmet from "helmet";
import mongoose from "mongoose";
import { ZodError, z } from "zod";
import type { Config } from "./config.js";
import { Chat, Feedback } from "./models.js";
import { RagUnavailableError, type RagClient } from "./ragClient.js";

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const clientIdSchema = z.string().uuid();
const chatBody = z.object({
  message: z.string().trim().min(3).max(1000),
  chatId: z.string().optional(),
});
const feedbackBody = z.object({
  chatId: z.string(),
  messageId: z.string(),
  value: z.enum(["up", "down"]),
  comment: z.string().trim().max(1000).optional(),
});

function objectId(value: string, what: string): mongoose.Types.ObjectId {
  if (!mongoose.isValidObjectId(value)) throw new HttpError(400, `Invalid ${what}`);
  return new mongoose.Types.ObjectId(value);
}

function clientId(header: string | undefined): string {
  const parsed = clientIdSchema.safeParse(header);
  if (!parsed.success) throw new HttpError(400, "Header 'x-client-id' must be a UUID");
  return parsed.data;
}

export function createApp(config: Config, rag: RagClient): Express {
  const app = express();
  app.disable("x-powered-by");
  app.use(helmet());
  app.use(cors({ origin: config.corsOrigin }));
  app.use(express.json({ limit: "20kb" }));
  app.use(
    "/api",
    rateLimit({
      windowMs: 60_000,
      limit: config.rateLimitPerMinute,
      standardHeaders: true,
      legacyHeaders: false,
      message: { error: "Too many requests, please slow down." },
    }),
  );

  app.get("/health", (_req, res) => {
    res.json({ status: "ok", mongo: mongoose.connection.readyState === 1 });
  });

  app.post("/api/chat", async (req, res) => {
    const owner = clientId(req.header("x-client-id"));
    const { message, chatId } = chatBody.parse(req.body);

    const chat = chatId
      ? await Chat.findOne({ _id: objectId(chatId, "chatId"), clientId: owner })
      : new Chat({ clientId: owner, title: message.slice(0, 60) });
    if (!chat) throw new HttpError(404, "Chat not found");

    // Call the RAG service first so a failure does not leave an unanswered question behind.
    const result = await rag.ask(message);
    chat.messages.push({ role: "user", content: message });
    chat.messages.push({
      role: "assistant",
      content: result.answer,
      sources: result.sources,
      answered: result.answered,
    });
    await chat.save();
    const reply = chat.messages[chat.messages.length - 1]!;
    res.status(chatId ? 200 : 201).json({
      chatId: chat.id as string,
      message: {
        id: String(reply._id),
        role: reply.role,
        content: reply.content,
        sources: reply.sources,
        answered: reply.answered,
      },
    });
  });

  app.get("/api/chats", async (req, res) => {
    const owner = clientId(req.header("x-client-id"));
    const chats = await Chat.find({ clientId: owner })
      .sort({ updatedAt: -1 })
      .limit(50)
      .select("title updatedAt");
    res.json({ chats: chats.map((c) => ({ id: c.id as string, title: c.title, updatedAt: c.updatedAt })) });
  });

  app.get("/api/chats/:id", async (req, res) => {
    const owner = clientId(req.header("x-client-id"));
    const chat = await Chat.findOne({ _id: objectId(req.params.id ?? "", "chat id"), clientId: owner });
    if (!chat) throw new HttpError(404, "Chat not found");
    res.json({
      id: chat.id as string,
      title: chat.title,
      messages: chat.messages.map((m) => ({
        id: String(m._id),
        role: m.role,
        content: m.content,
        sources: m.sources,
        answered: m.answered,
        feedback: m.feedback ?? null,
      })),
    });
  });

  app.post("/api/feedback", async (req, res) => {
    const owner = clientId(req.header("x-client-id"));
    const body = feedbackBody.parse(req.body);
    const chatOid = objectId(body.chatId, "chatId");
    const messageOid = objectId(body.messageId, "messageId");
    const updated = await Chat.updateOne(
      { _id: chatOid, clientId: owner, "messages._id": messageOid, "messages.role": "assistant" },
      { $set: { "messages.$.feedback": body.value } },
    );
    if (updated.matchedCount === 0) throw new HttpError(404, "Message not found");
    await Feedback.findOneAndUpdate(
      { chatId: chatOid, messageId: messageOid, clientId: owner },
      { value: body.value, comment: body.comment },
      { upsert: true },
    );
    res.status(201).json({ ok: true });
  });

  app.use((_req, _res, next) => next(new HttpError(404, "Route not found")));

  // Error middleware: every failure becomes a JSON { error } response.
  // Express identifies error middleware by its 4-argument signature, so `_next` must stay.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const onError: ErrorRequestHandler = (err: unknown, _req, res, _next) => {
    if (err instanceof ZodError) {
      res.status(400).json({ error: "Invalid request", details: err.issues.map((i) => `${i.path.join(".")}: ${i.message}`) });
    } else if (err instanceof HttpError) {
      res.status(err.status).json({ error: err.message });
    } else if (err instanceof RagUnavailableError) {
      res.status(502).json({ error: "The answering service is currently unavailable. Please try again." });
    } else if ((err as { type?: string }).type === "entity.parse.failed") {
      res.status(400).json({ error: "Malformed JSON body" });
    } else if ((err as { type?: string }).type === "entity.too.large") {
      res.status(413).json({ error: "Request body too large" });
    } else {
      console.error(err);
      res.status(500).json({ error: "Internal server error" });
    }
  };
  app.use(onError);
  return app;
}
