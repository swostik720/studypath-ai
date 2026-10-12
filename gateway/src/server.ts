import mongoose from "mongoose";
import { createApp } from "./app.js";
import { loadConfig } from "./config.js";
import { HttpRagClient } from "./ragClient.js";

async function main(): Promise<void> {
  const config = loadConfig();
  await mongoose.connect(config.mongoUrl);
  const app = createApp(config, new HttpRagClient(config.ragUrl, config.ragTimeoutMs));
  app.listen(config.port, () => console.log(`Gateway listening on :${config.port}`));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
