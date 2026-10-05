import { describe, expect, it } from "vitest";
import { describeCron, parseCron, serializeCron } from "./cron";

describe("cron utils", () => {
  it("serializeCron and parseCron roundtrip for daily", () => {
    const expr = serializeCron("daily", { hour: 9, minute: 30 });
    expect(expr).toBe("30 9 * * *");

    const parsed = parseCron("30 9 * * *");
    expect(parsed.preset).toBe("daily");
    expect(parsed.parts.hour).toBe(9);
    expect(parsed.parts.minute).toBe(30);

    expect(describeCron(expr)).toBe("每天 09:30");
  });

  it("serializeCron and parseCron roundtrip for hourly", () => {
    const expr = serializeCron("hourly", { minute: 15 });
    expect(expr).toBe("15 * * * *");

    const parsed = parseCron("15 * * * *");
    expect(parsed.preset).toBe("hourly");
    expect(parsed.parts.minute).toBe(15);

    expect(describeCron(expr)).toBe("每小时第 15 分钟");
  });

  it("serializeCron and parseCron roundtrip for weekly", () => {
    const expr = serializeCron("weekly", {
      hour: 10,
      minute: 0,
      weekdays: ["mon", "wed", "fri"],
    });
    expect(expr).toBe("0 10 * * 1,3,5");

    const parsed = parseCron("0 10 * * 1,3,5");
    expect(parsed.preset).toBe("weekly");
    expect(parsed.parts.weekdays).toEqual(["mon", "wed", "fri"]);
    expect(parsed.parts.hour).toBe(10);
    expect(parsed.parts.minute).toBe(0);

    expect(describeCron(expr)).toBe("每周一、周三、周五 10:00");
  });

  it("serializeCron and parseCron roundtrip for monthly", () => {
    const expr = serializeCron("monthly", {
      hour: 8,
      minute: 0,
      dayOfMonth: 15,
    });
    expect(expr).toBe("0 8 15 * *");

    const parsed = parseCron("0 8 15 * *");
    expect(parsed.preset).toBe("monthly");
    expect(parsed.parts.dayOfMonth).toBe(15);

    expect(describeCron(expr)).toBe("每月 15 日 08:00");
  });

  it("handles custom or non-standard cron", () => {
    const custom = "*/10 * * * *";
    const parsed = parseCron(custom);
    expect(parsed.preset).toBe("custom");
    expect(parsed.parts.raw).toBe(custom);
    expect(describeCron(custom)).toBe("自定义 (*/10 * * * *)");
  });
});
