import { NextResponse } from "next/server";

import { logFrontendClient, logFrontendServer } from "@/lib/server-logger";

type ClientLogBody = {
  level?: "debug" | "info" | "warn" | "error";
  event?: string;
  message?: string;
  context?: Record<string, unknown>;
  page?: string;
  query?: string;
};

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as ClientLogBody;
    const bodySize = JSON.stringify(body).length;
    if (bodySize > 32_000) {
      return NextResponse.json({ ok: false, error: "payload_too_large" }, { status: 413 });
    }

    const level = body.level ?? "info";
    const event = body.event ?? "client_event";
    const message = body.message ?? "";

    await logFrontendServer({
      level: "debug",
      event: "client_log_received",
      message: "Client log payload received",
      context: {
        event,
        level,
      },
    });

    await logFrontendClient({
      level,
      event,
      message,
      context: {
        ...(body.context ?? {}),
        page: body.page,
        query: body.query,
      },
    });

    return NextResponse.json({ ok: true });
  } catch (error) {
    await logFrontendServer({
      level: "error",
      event: "client_log_ingest_failed",
      message: "Failed to ingest client log",
      context: {
        error: String(error),
      },
    });
    return NextResponse.json({ ok: false }, { status: 500 });
  }
}
