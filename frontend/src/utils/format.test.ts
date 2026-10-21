import { describe, expect, it } from "vitest";
import { minutesLabel, relativeTime, scoreLevel } from "./format";

describe("format", () => {
  const now = new Date("2026-10-21T12:00:00Z");

  it("relativeTime en pasado y futuro", () => {
    expect(relativeTime("2026-10-21T11:55:00Z", now)).toBe("hace 5 min");
    expect(relativeTime("2026-10-21T14:00:00Z", now)).toBe("en 2 h");
    expect(relativeTime("2026-10-18T12:00:00Z", now)).toBe("hace 3 días");
    expect(relativeTime(null, now)).toBe("—");
  });

  it("scoreLevel", () => {
    expect([scoreLevel(80), scoreLevel(40), scoreLevel(5)]).toEqual(["high", "mid", "low"]);
  });

  it("minutesLabel", () => {
    expect(minutesLabel(0)).toBe("Desactivada");
    expect(minutesLabel(30)).toBe("Cada 30 min");
    expect(minutesLabel(390)).toBe("Cada 6.5 h");
    expect(minutesLabel(1440)).toBe("Una vez al día");
  });
});
