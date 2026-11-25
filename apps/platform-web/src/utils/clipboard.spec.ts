import { afterEach, describe, expect, it, vi } from "vitest";
import { copyText } from "./clipboard";

describe("copyText", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("uses navigator.clipboard.writeText when available", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });

    const ok = await copyText("70f0ab34-bd4e-439b-b8ce-20a3957557f9");

    expect(ok).toBe(true);
    expect(writeText).toHaveBeenCalledWith(
      "70f0ab34-bd4e-439b-b8ce-20a3957557f9",
    );
  });

  it("falls back to document.execCommand('copy') when navigator.clipboard is unavailable (HTTP)", async () => {
    vi.stubGlobal("navigator", {});
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, "execCommand", {
      value: execCommand,
      configurable: true,
    });

    const ok = await copyText("70f0ab34-bd4e-439b-b8ce-20a3957557f9");

    expect(ok).toBe(true);
    expect(execCommand).toHaveBeenCalledWith("copy");
  });
});
