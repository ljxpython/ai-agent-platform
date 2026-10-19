import axios from "axios";
import { afterEach, expect, it, vi } from "vitest";
import {
  clearTokenSet,
  getAccessToken,
  setTokenSet,
} from "@/services/auth/token";
import { platformHttpClient, refreshAccessToken } from "./client";

afterEach(() => {
  vi.restoreAllMocks();
  clearTokenSet();
});

it("late successful REST responses cannot cross a logout/login boundary", async () => {
  setTokenSet({
    accessToken: "old",
    refreshToken: "old-refresh",
    tokenType: "bearer",
  });
  let complete!: () => void;
  const request = platformHttpClient.get("/probe", {
    adapter: (config) =>
      new Promise((resolve) => {
        complete = () =>
          resolve({
            config,
            status: 200,
            statusText: "OK",
            headers: {},
            data: "old account",
          });
      }),
  });
  const result = expect(request).rejects.toThrow("登录会话已变更");
  await vi.waitFor(() => expect(complete).toBeTypeOf("function"));
  clearTokenSet();
  setTokenSet({
    accessToken: "new",
    refreshToken: "new-refresh",
    tokenType: "bearer",
  });
  complete();
  await result;
  expect(getAccessToken()).toBe("new");
});

it("concurrent refresh is coalesced and an old refresh cannot replace the new session", async () => {
  setTokenSet({
    accessToken: "old",
    refreshToken: "old-refresh",
    tokenType: "bearer",
  });
  let complete!: (value: unknown) => void;
  const post = vi.spyOn(axios, "post").mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  const first = refreshAccessToken();
  const second = refreshAccessToken();
  expect(post).toHaveBeenCalledTimes(1);
  clearTokenSet();
  setTokenSet({
    accessToken: "new",
    refreshToken: "new-refresh",
    tokenType: "bearer",
  });
  complete({ data: { access_token: "late", refresh_token: "late-refresh" } });
  expect(await Promise.all([first, second])).toEqual(["", ""]);
  expect(getAccessToken()).toBe("new");
});

it.each([
  new Error("offline"),
  new axios.AxiosError("unavailable", undefined, undefined, undefined, {
    status: 503,
  } as never),
])("preserves tokens on transient refresh failure", async (error) => {
  setTokenSet({
    accessToken: "expired",
    refreshToken: "keep",
    tokenType: "bearer",
  });
  vi.spyOn(axios, "post").mockRejectedValue(error);
  await expect(refreshAccessToken()).rejects.toMatchObject({
    code: "auth_refresh_unavailable",
    status: 503,
  });
  expect(getAccessToken()).toBe("expired");
});

it("records failed HTTP requests to errorRingBuffer with requestId and details", async () => {
  const { errorRingBuffer } =
    await import("@/services/observability/error-buffer");
  errorRingBuffer.clear();

  const failRequest = platformHttpClient.get("/api/test-failure", {
    adapter: (config) =>
      Promise.reject(
        new axios.AxiosError(
          "Request failed with status code 502",
          "ERR_BAD_RESPONSE",
          config,
          undefined,
          {
            status: 502,
            statusText: "Bad Gateway",
            headers: { "x-request-id": "req-trace-502-xyz" },
            data: {
              error: {
                code: "runtime_execution_failed",
                message: "Remote sandbox unavailable",
              },
              request_id: "req-trace-502-xyz",
            },
          } as never,
        ),
      ),
  });

  await expect(failRequest).rejects.toThrow();

  const recorded = errorRingBuffer.getLatest();
  expect(recorded).not.toBeNull();
  expect(recorded?.status).toBe(502);
  expect(recorded?.requestId).toBe("req-trace-502-xyz");
  expect(recorded?.code).toBe("runtime_execution_failed");
  expect(recorded?.message).toBe("Remote sandbox unavailable");
});
