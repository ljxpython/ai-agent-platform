import { describe, expect, it } from "vitest";

import { resolveBrowserApiBaseUrl, resolveBrowserMlflowBaseUrl } from "./env";

describe("resolveBrowserApiBaseUrl", () => {
  it("keeps an explicit loopback API origin outside dev proxy mode", () => {
    expect(
      resolveBrowserApiBaseUrl("http://127.0.0.1:2142", {
        preferSameOriginLoopbackProxy: false,
      }),
    ).toBe("http://127.0.0.1:2142");
  });

  it("rewrites loopback API origins to same-origin only in dev proxy mode", () => {
    expect(
      resolveBrowserApiBaseUrl("http://127.0.0.1:2142", {
        preferSameOriginLoopbackProxy: true,
      }),
    ).toBe(window.location.origin);
  });
});

describe("resolveBrowserMlflowBaseUrl", () => {
  it("keeps loopback target when browser is on loopback origin (local dev)", () => {
    expect(
      resolveBrowserMlflowBaseUrl("http://127.0.0.1:9128", {
        locationOrigin: "http://localhost:3000",
      }),
    ).toBe("http://127.0.0.1:9128");

    expect(
      resolveBrowserMlflowBaseUrl("http://127.0.0.1:9128", {
        locationOrigin: "http://127.0.0.1:3000",
      }),
    ).toBe("http://127.0.0.1:9128");
  });

  it("rewrites loopback target to remote server host when page is hosted on remote IP", () => {
    expect(
      resolveBrowserMlflowBaseUrl("http://127.0.0.1:9128", {
        locationOrigin: "http://49.233.222.54",
      }),
    ).toBe("http://49.233.222.54:9128");

    expect(
      resolveBrowserMlflowBaseUrl("http://localhost:9128", {
        locationOrigin: "http://49.233.222.54:80",
      }),
    ).toBe("http://49.233.222.54:9128");
  });

  it("rewrites loopback target to remote domain hostname when page is hosted on a domain", () => {
    expect(
      resolveBrowserMlflowBaseUrl("http://127.0.0.1:9128", {
        locationOrigin: "https://ai.example.com",
      }),
    ).toBe("http://ai.example.com:9128");
  });

  it("preserves explicit non-loopback configured target", () => {
    expect(
      resolveBrowserMlflowBaseUrl("http://custom-evalflow.example.com:9128", {
        locationOrigin: "http://49.233.222.54",
      }),
    ).toBe("http://custom-evalflow.example.com:9128");
  });

  it("handles empty value and falls back to default with loopback adaptation", () => {
    expect(
      resolveBrowserMlflowBaseUrl("", {
        locationOrigin: "http://49.233.222.54",
      }),
    ).toBe("http://49.233.222.54:9128");
  });
});
