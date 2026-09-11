import axios from "axios";
import { afterEach, expect, it, vi } from "vitest";
import { clearTokenSet, getAccessToken, setTokenSet } from "@/services/auth/token";
import { platformHttpClient, refreshAccessToken } from "./client";

afterEach(() => { vi.restoreAllMocks(); clearTokenSet(); });

it("late successful REST responses cannot cross a logout/login boundary", async () => {
  setTokenSet({ accessToken: "old", refreshToken: "old-refresh", tokenType: "bearer" });
  let complete!: () => void;
  const request = platformHttpClient.get("/probe", { adapter: config => new Promise(resolve => {
    complete = () => resolve({ config, status: 200, statusText: "OK", headers: {}, data: "old account" });
  }) });
  const result = expect(request).rejects.toThrow("登录会话已变更");
  await vi.waitFor(() => expect(complete).toBeTypeOf("function"));
  clearTokenSet();
  setTokenSet({ accessToken: "new", refreshToken: "new-refresh", tokenType: "bearer" });
  complete();
  await result;
  expect(getAccessToken()).toBe("new");
});

it("concurrent refresh is coalesced and an old refresh cannot replace the new session", async () => {
  setTokenSet({ accessToken: "old", refreshToken: "old-refresh", tokenType: "bearer" });
  let complete!: (value: unknown) => void;
  const post = vi.spyOn(axios, "post").mockImplementationOnce(() => new Promise(resolve => { complete = resolve; }));
  const first = refreshAccessToken();
  const second = refreshAccessToken();
  expect(post).toHaveBeenCalledTimes(1);
  clearTokenSet();
  setTokenSet({ accessToken: "new", refreshToken: "new-refresh", tokenType: "bearer" });
  complete({ data: { access_token: "late", refresh_token: "late-refresh" } });
  expect(await Promise.all([first, second])).toEqual(["", ""]);
  expect(getAccessToken()).toBe("new");
});
