type LogLevel = "debug" | "info" | "warn" | "error";

type ClientLogInput = {
  level: LogLevel;
  event: string;
  message: string;
  context?: Record<string, unknown>;
};

const CLIENT_LOG_ENDPOINT = "/api/client-logs";

function emitConsole(level: LogLevel, event: string, message: string, context?: Record<string, unknown>) {
  const payload = { event, message, ...(context ?? {}) };
  if (level === "debug") {
    console.debug(payload);
    return;
  }
  if (level === "info") {
    console.info(payload);
    return;
  }
  if (level === "warn") {
    console.warn(payload);
    return;
  }
  console.error(payload);
}

export async function logClient(input: ClientLogInput): Promise<void> {
  emitConsole(input.level, input.event, input.message, input.context);

  const payload = {
    ...input,
    page: typeof window !== "undefined" ? window.location.pathname : "",
    query: typeof window !== "undefined" ? window.location.search : "",
  };

  try {
    await fetch(CLIENT_LOG_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      keepalive: true,
    });
  } catch {
    return;
  }
}
