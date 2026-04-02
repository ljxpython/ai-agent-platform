"use client";

import { useEffect } from "react";

import { logClient } from "@/lib/client-logger";

export function LogBootstrap() {
  useEffect(() => {
    const onError = (event: ErrorEvent) => {
      logClient({
        level: "error",
        event: "window_error",
        message: event.message || "Unhandled window error",
        context: {
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno,
        },
      });
    };

    const onUnhandledRejection = (event: PromiseRejectionEvent) => {
      logClient({
        level: "error",
        event: "window_unhandled_rejection",
        message: "Unhandled promise rejection",
        context: {
          reason: String(event.reason),
        },
      });
    };

    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandledRejection);

    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
    };
  }, []);

  return null;
}
