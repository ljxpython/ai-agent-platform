import { describe, expect, it } from "vitest";
import { AxiosError } from "axios";
import {
  extractPlatformHttpError,
  formatPlatformHttpErrorMessage,
  unwrapPlatformHttpError,
} from "./http-error";

const payload = {
  error: {
    code: "thread_provisioning_unconfirmed",
    message: "Reconcile first",
    details: [
      { loc: ["body", "id"], type: "missing", message: "Field required" },
    ],
    extra: { thread_id: "11111111-1111-4111-8111-111111111111" },
  },
  request_id: "req-1",
};

describe("platform HTTP errors", () => {
  it("keeps SDK and Axios fields without using Axios transport code", async () => {
    const sdk = extractPlatformHttpError(
      Object.assign(new Error("HTTP 503"), {
        status: 503,
        text: JSON.stringify(payload),
      }),
    );
    const axios = extractPlatformHttpError(
      new AxiosError("Request failed", "ERR_BAD_RESPONSE", {}, undefined, {
        status: 503,
        data: payload,
        headers: {},
        config: { headers: {} },
        statusText: "",
      }),
    );
    expect(sdk).toMatchObject({
      status: 503,
      code: payload.error.code,
      requestId: "req-1",
      extra: payload.error.extra,
    });
    expect(axios).toMatchObject({
      code: payload.error.code,
      details: payload.error.details,
    });
    expect(
      await unwrapPlatformHttpError({
        response: { status: 503, data: new Blob([JSON.stringify(payload)]) },
      }),
    ).toMatchObject({
      code: payload.error.code,
      requestId: "req-1",
      extra: payload.error.extra,
    });
  });

  it("bounds body parsing and never displays HTML or invalid IDs", () => {
    expect(
      extractPlatformHttpError({ status: 502, text: "<html>secret</html>" })
        .message,
    ).toBe("请求失败（HTTP 502）");
    expect(
      extractPlatformHttpError({ status: 502, message: "<html>secret</html>" })
        .message,
    ).toBe("请求失败（HTTP 502）");
    expect(
      extractPlatformHttpError(new TypeError("Failed to fetch")).message,
    ).toBe("网络连接失败，请检查网络后重试");
    expect(
      extractPlatformHttpError({ status: 502, text: "x".repeat(65537) }).code,
    ).toBeUndefined();
    expect(
      formatPlatformHttpErrorMessage({
        response: { status: 503, data: payload },
      }),
    ).toContain("请求编号：req-1");
    expect(
      formatPlatformHttpErrorMessage({
        response: { status: 503, data: { ...payload, request_id: "bad\nID" } },
      }),
    ).not.toContain("请求编号");
    expect(
      extractPlatformHttpError(
        Object.assign(new Error("cancelled"), { name: "AbortError" }),
      ).cancelled,
    ).toBe(true);
  });
});
