import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChangelogEntry, ChangelogResponse, JobStatus } from "../models";
import {
  cancelResult,
  clearNewFlags,
  confirmResult,
  connectionChange,
  errorText,
  initialFullscreen,
  jobOutcomes,
  markChangelogSeen,
  needsMarkSeen,
  newRunDetected,
  nextPhraseIndex,
  pageReadyDelay,
  parseSyncEvent,
  randomPhraseIndex,
  secondsSince,
  shouldAutoOpenChangelog,
  shouldStartSync,
} from "./store-logic";

const seq = (...values: number[]) => {
  let i = 0;
  return () => values[i++]!;
};

describe("initialFullscreen", () => {
  it("is the server's default when the user never chose", () => {
    expect(initialFullscreen(null, true)).toBe(true);
    expect(initialFullscreen(null, false)).toBe(false);
  });

  it("is the user's saved choice, whatever the server says", () => {
    expect(initialFullscreen("true", false)).toBe(true);
    expect(initialFullscreen("false", true)).toBe(false);
  });

  it("is off for any other saved text", () => {
    expect(initialFullscreen("", true)).toBe(false);
    expect(initialFullscreen("yes", true)).toBe(false);
  });
});

describe("connectionChange", () => {
  it("only sets a baseline the first time the server is seen up, with no message", () => {
    expect(connectionChange(null, true)).toEqual({ wasConnected: true, notice: null });
  });

  it("stays unknown while the server has not been seen up", () => {
    expect(connectionChange(null, false)).toEqual({ wasConnected: null, notice: null });
  });

  it("says nothing while the connection does not change", () => {
    expect(connectionChange(true, true)).toEqual({ wasConnected: true, notice: null });
    expect(connectionChange(false, false)).toEqual({ wasConnected: false, notice: null });
  });

  it("announces a lost connection as an error", () => {
    expect(connectionChange(true, false)).toEqual({
      wasConnected: false,
      notice: { message: "Server connection lost", type: "error" },
    });
  });

  it("announces a restored connection as a success", () => {
    expect(connectionChange(false, true)).toEqual({
      wasConnected: true,
      notice: { message: "Server connection restored", type: "success" },
    });
  });

  it("does not announce a first failure as a loss, but does announce the first recovery after one as nothing", () => {
    const first = connectionChange(null, false);
    expect(connectionChange(first.wasConnected, true)).toEqual({ wasConnected: true, notice: null });
  });
});

describe("newRunDetected", () => {
  it("is true when a job that was complete reports it is not", () => {
    expect(newRunDetected(true, false)).toBe(true);
  });

  it("is false otherwise", () => {
    expect(newRunDetected(true, true)).toBe(false);
    expect(newRunDetected(true, undefined)).toBe(false);
    expect(newRunDetected(false, false)).toBe(false);
    expect(newRunDetected(false, true)).toBe(false);
    expect(newRunDetected(false, undefined)).toBe(false);
  });
});

describe("shouldStartSync", () => {
  it("is true only with no stream open, auto-refresh on, and the job still running", () => {
    expect(shouldStartSync(false, true, false)).toBe(true);
  });

  it.each([
    [true, true, false],
    [false, false, false],
    [false, true, true],
  ])("is false for source %s, auto %s, complete %s", (hasSource, auto, complete) => {
    expect(shouldStartSync(hasSource, auto, complete)).toBe(false);
  });
});

describe("parseSyncEvent", () => {
  const status = (over: Partial<JobStatus> = {}) => ({ is_complete: false, ...over }) as JobStatus;

  it("reads a start message", () => {
    expect(parseSyncEvent('{"type":"start"}')).toEqual({ kind: "start" });
  });

  it("reads progress, including zero", () => {
    expect(parseSyncEvent('{"type":"progress","value":42}')).toEqual({ kind: "progress", value: 42 });
    expect(parseSyncEvent('{"type":"progress","value":0}')).toEqual({ kind: "progress", value: 0 });
  });

  it("ignores progress with no value", () => {
    expect(parseSyncEvent('{"type":"progress"}')).toEqual({ kind: "none" });
  });

  it("reads the final status and whether the job is complete", () => {
    const raw = JSON.stringify({ type: "final", status: status({ is_complete: true }) });
    expect(parseSyncEvent(raw)).toEqual({ kind: "final", status: status({ is_complete: true }), isComplete: true });
    expect(parseSyncEvent(JSON.stringify({ type: "final", status: status() }))).toMatchObject({ isComplete: false });
  });

  it("takes a final message with no status, or no completion flag, as not complete", () => {
    expect(parseSyncEvent('{"type":"final"}')).toEqual({ kind: "final", status: undefined, isComplete: false });
    expect(parseSyncEvent('{"type":"final","status":{}}')).toMatchObject({ isComplete: false });
  });

  it("ignores any other type", () => {
    for (const raw of ['{"type":"other"}', "{}", '{"type":null}']) expect(parseSyncEvent(raw)).toEqual({ kind: "none" });
  });

  it("ignores json that is a plain value", () => {
    for (const raw of ["5", '"str"', "true"]) expect(parseSyncEvent(raw)).toEqual({ kind: "none" });
  });

  it("throws for text that is not json, or is json null", () => {
    for (const raw of ["garbage", "{broken", "", "null"]) expect(() => parseSyncEvent(raw)).toThrow();
  });
});

describe("jobOutcomes", () => {
  it("is the failed and errored trial numbers as numbers", () => {
    expect(jobOutcomes({ failure_tns: ["3", "4"], error_tns: ["9"] } as unknown as JobStatus)).toEqual({ failure: [3, 4], error: [9] });
  });

  it("keeps numbers that are already numbers", () => {
    expect(jobOutcomes({ failure_tns: [1, 2], error_tns: [5] } as unknown as JobStatus)).toEqual({ failure: [1, 2], error: [5] });
  });

  it("is empty for lists that are missing", () => {
    expect(jobOutcomes({} as JobStatus)).toEqual({ failure: [], error: [] });
    expect(jobOutcomes({ failure_tns: null, error_tns: null } as unknown as JobStatus)).toEqual({ failure: [], error: [] });
  });

  it("keeps the two lists apart", () => {
    const out = jobOutcomes({ failure_tns: ["1"], error_tns: [] } as unknown as JobStatus);
    expect(out.failure).toEqual([1]);
    expect(out.error).toEqual([]);
  });
});

describe("secondsSince", () => {
  it("is whole seconds, rounded down", () => {
    expect(secondsSince(0, 999)).toBe(0);
    expect(secondsSince(0, 1000)).toBe(1);
    expect(secondsSince(0, 1999)).toBe(1);
    expect(secondsSince(1000, 3500)).toBe(2);
    expect(secondsSince(5000, 5000)).toBe(0);
  });
});

describe("pageReadyDelay", () => {
  it("keeps the loading screen up for two seconds from when loading started", () => {
    expect(pageReadyDelay(false, 1000, 1000)).toBe(2000);
    expect(pageReadyDelay(false, 1000, 1500)).toBe(1500);
    expect(pageReadyDelay(false, 1000, 2999)).toBe(1);
  });

  it("is no wait once two seconds have passed", () => {
    expect(pageReadyDelay(false, 1000, 3000)).toBe(0);
    expect(pageReadyDelay(false, 1000, 9000)).toBe(0);
  });

  it("is never negative", () => {
    expect(pageReadyDelay(false, 0, 100_000)).toBe(0);
    expect(pageReadyDelay(true, 0, 100_000)).toBe(0);
  });

  it("is no wait when forced", () => {
    expect(pageReadyDelay(true, 1000, 1000)).toBe(0);
  });
});

describe("loading phrases", () => {
  it("picks a phrase from the whole list", () => {
    expect(randomPhraseIndex(43, () => 0)).toBe(0);
    expect(randomPhraseIndex(43, () => 0.5)).toBe(21);
    expect(randomPhraseIndex(43, () => 0.999999)).toBe(42);
  });

  it("picks a different phrase from the one showing", () => {
    // 0.5 of 10 is index 5, the current one, so it draws again
    expect(nextPhraseIndex(5, 10, seq(0.5, 0.5, 0.9))).toBe(9);
  });

  it("takes the first draw when it differs", () => {
    expect(nextPhraseIndex(5, 10, seq(0.1, 0.9))).toBe(1);
  });

  it("can pick the phrase before and after the current one", () => {
    expect(nextPhraseIndex(5, 10, seq(0.4))).toBe(4);
    expect(nextPhraseIndex(5, 10, seq(0.6))).toBe(6);
  });
});

describe("changelog decisions", () => {
  const entry = (over: Partial<ChangelogEntry> = {}): ChangelogEntry => ({ version: "1.0.0", date: null, bullets: [], is_new: false, ...over });
  const data = (over: Partial<ChangelogResponse> = {}): ChangelogResponse => ({
    entries: [entry({ is_new: true })],
    installed_version: "1.0.0",
    latest_version: "1.0.0",
    update_available: false,
    show_whats_changed: true,
    is_localhost: false,
    error: null,
    ...over,
  });

  describe("shouldAutoOpenChangelog", () => {
    it("is true with unseen entries, the popup on, and settings closed", () => {
      expect(shouldAutoOpenChangelog(data(), false)).toBe(true);
    });

    it("is false when the user turned the popup off", () => {
      expect(shouldAutoOpenChangelog(data({ show_whats_changed: false }), false)).toBe(false);
    });

    it("is false while the settings panel is open", () => {
      expect(shouldAutoOpenChangelog(data(), true)).toBe(false);
    });

    it("is false with nothing new", () => {
      expect(shouldAutoOpenChangelog(data({ entries: [entry()] }), false)).toBe(false);
      expect(shouldAutoOpenChangelog(data({ entries: [] }), false)).toBe(false);
    });

    it("is true when only one of several entries is new", () => {
      expect(shouldAutoOpenChangelog(data({ entries: [entry(), entry({ is_new: true }), entry()] }), false)).toBe(true);
    });
  });

  describe("needsMarkSeen", () => {
    it("is true with a latest version and something new", () => {
      expect(needsMarkSeen("1.2.0", [entry({ is_new: true })])).toBe(true);
    });

    it("is false with no latest version, or nothing new", () => {
      expect(needsMarkSeen(null, [entry({ is_new: true })])).toBe(false);
      expect(needsMarkSeen("", [entry({ is_new: true })])).toBe(false);
      expect(needsMarkSeen("1.2.0", [entry()])).toBe(false);
      expect(needsMarkSeen("1.2.0", [])).toBe(false);
    });
  });

  describe("clearNewFlags", () => {
    it("marks every entry seen and keeps the rest of it", () => {
      const entries = [entry({ version: "2", is_new: true, bullets: ["a"], date: "d" }), entry({ version: "1" })];
      expect(clearNewFlags(entries)).toEqual([
        { version: "2", date: "d", bullets: ["a"], is_new: false },
        { version: "1", date: null, bullets: [], is_new: false },
      ]);
    });

    it("leaves the original entries alone", () => {
      const entries = [entry({ is_new: true })];
      const out = clearNewFlags(entries);
      expect(entries[0]!.is_new).toBe(true);
      expect(out[0]).not.toBe(entries[0]);
    });
  });
});

describe("errorText", () => {
  it("is an error's message", () => {
    expect(errorText(new Error("boom"), "fallback")).toBe("boom");
    expect(errorText(new TypeError("bad type"), "fallback")).toBe("bad type");
  });

  it("is the fallback for anything that is not an error", () => {
    for (const thrown of ["text", 5, null, undefined, { message: "looks like one" }]) {
      expect(errorText(thrown, "fallback")).toBe("fallback");
    }
  });
});

describe("dialog answers", () => {
  it("confirming a plain dialog answers true", () => {
    expect(confirmResult(false, "ignored")).toBe(true);
  });

  it("confirming a prompt answers the trimmed text", () => {
    expect(confirmResult(true, "  hello  ")).toBe("hello");
    expect(confirmResult(true, "x")).toBe("x");
  });

  it("confirming a prompt with nothing typed answers null", () => {
    expect(confirmResult(true, "")).toBeNull();
    expect(confirmResult(true, "   ")).toBeNull();
  });

  it("cancelling answers false for a plain dialog and null for a prompt", () => {
    expect(cancelResult(false)).toBe(false);
    expect(cancelResult(true)).toBeNull();
  });
});

describe("markChangelogSeen", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the version to the server and is true when it took", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    expect(await markChangelogSeen("1.2.3")).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/changelog/mark-seen");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body as string)).toEqual({ version: "1.2.3" });
  });

  it("is false for an error response, which is a request that did not take", async () => {
    for (const status of [400, 404, 500, 503]) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status }));
      expect(await markChangelogSeen("1.2.3"), String(status)).toBe(false);
    }
  });

  it("is false when the request never got there", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    expect(await markChangelogSeen("1.2.3")).toBe(false);
  });
});
