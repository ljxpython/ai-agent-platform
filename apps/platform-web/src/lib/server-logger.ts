import { appendFile, mkdir } from "node:fs/promises";
import path from "node:path";

type LogLevel = "debug" | "info" | "warn" | "error";

type LogPayload = {
  level: LogLevel;
  event: string;
  message: string;
  context?: Record<string, unknown>;
};

function resolveLogsDir(): string {
  const dir = process.env.FRONTEND_LOGS_DIR ?? "../logs";
  return path.resolve(process.cwd(), dir);
}

function frontendServerLogFile(): string {
  return process.env.FRONTEND_SERVER_LOG_FILE ?? "frontend-server.log";
}

function frontendClientLogFile(): string {
  return process.env.FRONTEND_CLIENT_LOG_FILE ?? "frontend-client.log";
}

async function appendLine(fileName: string, payload: LogPayload): Promise<void> {
  const logsDir = resolveLogsDir();
  await mkdir(logsDir, { recursive: true });

  const line = JSON.stringify({
    timestamp: new Date().toISOString(),
    ...payload,
  });

  await appendFile(path.join(logsDir, fileName), `${line}\n`, "utf8");
}

export async function logFrontendServer(payload: LogPayload): Promise<void> {
  await appendLine(frontendServerLogFile(), payload);
}

export async function logFrontendClient(payload: LogPayload): Promise<void> {
  await appendLine(frontendClientLogFile(), payload);
}
