import { Schema, model, type InferSchemaType } from "mongoose";

const sourceSchema = new Schema(
  {
    title: { type: String, required: true },
    url: { type: String, required: true },
    text: { type: String, required: true },
    score: { type: Number, required: true },
  },
  { _id: false },
);

const messageSchema = new Schema({
  role: { type: String, enum: ["user", "assistant"], required: true },
  content: { type: String, required: true },
  sources: { type: [sourceSchema], default: [] },
  answered: { type: Boolean, default: true },
  feedback: { type: String, enum: ["up", "down"], default: undefined },
  createdAt: { type: Date, default: () => new Date() },
});

const chatSchema = new Schema(
  {
    // Anonymous browser id (UUID kept in localStorage by the frontend); there are no accounts.
    clientId: { type: String, required: true, index: true },
    title: { type: String, required: true },
    messages: { type: [messageSchema], default: [] },
  },
  { timestamps: true },
);

const feedbackSchema = new Schema(
  {
    chatId: { type: Schema.Types.ObjectId, ref: "Chat", required: true, index: true },
    messageId: { type: Schema.Types.ObjectId, required: true },
    clientId: { type: String, required: true },
    value: { type: String, enum: ["up", "down"], required: true },
    comment: { type: String, maxlength: 1000 },
  },
  { timestamps: true },
);

export const Chat = model("Chat", chatSchema);
export const Feedback = model("Feedback", feedbackSchema);
export type ChatDoc = InferSchemaType<typeof chatSchema>;
