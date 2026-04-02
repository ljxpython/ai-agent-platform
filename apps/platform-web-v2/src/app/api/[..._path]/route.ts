import { initApiPassthrough } from "langgraph-nextjs-api-passthrough";
import type { NextRequest } from "next/server";
import { logFrontendServer } from "@/lib/server-logger";

const passthrough = initApiPassthrough({
  apiUrl: process.env.LANGGRAPH_API_URL ?? "remove-me",
  apiKey: process.env.LANGSMITH_API_KEY ?? "remove-me",
  runtime: "nodejs",
});

export const runtime = "nodejs";

async function withServerLog(
  method: string,
  request: NextRequest,
  handler: (request: NextRequest) => Response | Promise<Response>,
) {
  const started = Date.now();
  const path = new URL(request.url).pathname;

  await logFrontendServer({
    level: "info",
    event: "frontend_passthrough_request",
    message: "Passthrough request started",
    context: {
      method,
      path,
    },
  });

  try {
    const response = await handler(request);
    await logFrontendServer({
      level: "info",
      event: "frontend_passthrough_response",
      message: "Passthrough request finished",
      context: {
        method,
        path,
        status: response.status,
        duration_ms: Date.now() - started,
      },
    });
    return response;
  } catch (error) {
    await logFrontendServer({
      level: "error",
      event: "frontend_passthrough_error",
      message: "Passthrough request failed",
      context: {
        method,
        path,
        duration_ms: Date.now() - started,
        error: String(error),
      },
    });
    throw error;
  }
}

export async function GET(request: NextRequest) {
  return withServerLog("GET", request, passthrough.GET);
}

export async function POST(request: NextRequest) {
  return withServerLog("POST", request, passthrough.POST);
}

export async function PUT(request: NextRequest) {
  return withServerLog("PUT", request, passthrough.PUT);
}

export async function PATCH(request: NextRequest) {
  return withServerLog("PATCH", request, passthrough.PATCH);
}

export async function DELETE(request: NextRequest) {
  return withServerLog("DELETE", request, passthrough.DELETE);
}

export async function OPTIONS(request: NextRequest) {
  return withServerLog("OPTIONS", request, passthrough.OPTIONS);
}
