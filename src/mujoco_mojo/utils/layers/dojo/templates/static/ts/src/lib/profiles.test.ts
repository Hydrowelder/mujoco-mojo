import { afterEach, describe, expect, it, vi } from "vitest";

import type { PlotConfig, YAxisConfig } from "./plot-config.generated";
import { DEFAULT_CONFIG } from "./plot-defaults";
import type { PlotProfile } from "./plot-profile";
import type { PlotTab } from "./plot-tabs";
import {
  buildProfilePayload,
  profileActiveIndex,
  profileMissing,
  profileUrl,
  profileWarnings,
  saveProfileRequest,
  tabsFromProfile,
} from "./profiles";

afterEach(() => {
  vi.restoreAllMocks();
});

type Frame = [string | null, string | null];

const yAxis = (): YAxisConfig => ({ color: "#ff0000", filters: [] });

const config = (title: string, x: string, ys: string[], refFrame: Frame = [null, null]): PlotConfig => ({
  ...(JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as PlotConfig),
  title,
  xAxis: { col: x, filters: [] },
  yAxes: Object.fromEntries(ys.map((c) => [c, yAxis()])),
  refFrame,
});

const profileOf = (configs: PlotConfig[], over: Partial<PlotProfile> = {}): PlotProfile => ({
  version: 2,
  tabs: configs.map((c) => ({ config: c })),
  activeTabIndex: 0,
  vsEnabled: false,
  vsRange: [0, 10],
  vsPinned: [],
  ...over,
});

const tab = (id: string, c: PlotConfig = config("", "time", [])): PlotTab => ({
  id,
  config: c,
  data: { time: [1] },
  filterFingerprints: { a: "f" },
  xAxisFilterFingerprint: "[x]",
  historyStack: ["h"],
  historyIndex: 0,
  savedSnapshot: null,
});

// the trial these checks run against: a body with a position and an
// orientation, a wing with a position only, and a second orientation
const COLUMNS = ["time", "body:x", "body:y", "body:z", "body:w", "wing:x", "q:w"];

describe("profileUrl", () => {
  it("is the profiles route plus the name", () => {
    expect(profileUrl("baseline")).toBe("/mosaic/api/profiles/baseline");
  });

  it("keeps folder separators and encodes each segment", () => {
    expect(profileUrl("robotics/arm reach/v#2")).toBe("/mosaic/api/profiles/robotics/arm%20reach/v%232");
    expect(profileUrl("ü/100%")).toBe("/mosaic/api/profiles/%C3%BC/100%25");
  });

  it("keeps empty segments", () => {
    expect(profileUrl("a//b")).toBe("/mosaic/api/profiles/a//b");
  });
});

describe("saveProfileRequest", () => {
  const payload = profileOf([config("A", "time", ["a"])]);
  const replyWith = (status: number, json: () => Promise<unknown>) =>
    ({ ok: status >= 200 && status < 300, status, json }) as Response;
  const reply = (status: number, body: unknown = {}) => replyWith(status, () => Promise.resolve(body));

  const stubFetch = (...replies: Array<Response | Error>) => {
    const fn = vi.fn();
    for (const r of replies) {
      if (r instanceof Error) fn.mockRejectedValueOnce(r);
      else fn.mockResolvedValueOnce(r);
    }
    vi.stubGlobal("fetch", fn);
    return fn;
  };

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the payload to the profile's url, asking not to overwrite", async () => {
    const fetchMock = stubFetch(reply(200, { name: "My_Plots" }));
    const confirm = vi.fn();
    await saveProfileRequest("My Plots", payload, confirm);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/mosaic/api/profiles/My%20Plots?overwrite=false");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body as string)).toEqual(payload);
  });

  it("is saved under the name the server gives, without asking anything", async () => {
    stubFetch(reply(200, { name: "My_Plots" }));
    const confirm = vi.fn();
    expect(await saveProfileRequest("My Plots", payload, confirm)).toEqual({ saved: true, name: "My_Plots" });
    expect(confirm).not.toHaveBeenCalled();
  });

  it("asks with the stored name when the server finds one, and replaces it on yes", async () => {
    const fetchMock = stubFetch(reply(409, { detail: { name: "ab" } }), reply(200, { name: "ab" }));
    const confirm = vi.fn().mockResolvedValue(true);
    expect(await saveProfileRequest("a.b", payload, confirm)).toEqual({ saved: true, name: "ab" });
    expect(confirm).toHaveBeenCalledExactlyOnceWith("ab");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect((fetchMock.mock.calls[0] as [string])[0]).toBe("/mosaic/api/profiles/a.b?overwrite=false");
    // the second request is the one that may replace it
    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toBe("/mosaic/api/profiles/a.b");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(payload);
  });

  it("saves nothing more on no", async () => {
    const fetchMock = stubFetch(reply(409, { detail: { name: "ab" } }));
    const confirm = vi.fn().mockResolvedValue(false);
    expect(await saveProfileRequest("a.b", payload, confirm)).toEqual({ saved: false });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("asks with the typed name when the 409 does not say which is stored", async () => {
    for (const body of [{}, { detail: "taken" }, { detail: {} }]) {
      stubFetch(reply(409, body), reply(200, { name: "typed" }));
      const confirm = vi.fn().mockResolvedValue(true);
      await saveProfileRequest("typed", payload, confirm);
      expect(confirm).toHaveBeenCalledExactlyOnceWith("typed");
    }
  });

  it("still asks when the 409 has no readable body", async () => {
    const unreadable = replyWith(409, () => Promise.reject(new SyntaxError("bad json")));
    stubFetch(unreadable, reply(200, { name: "typed" }));
    const confirm = vi.fn().mockResolvedValue(true);
    expect(await saveProfileRequest("typed", payload, confirm)).toEqual({ saved: true, name: "typed" });
    expect(confirm).toHaveBeenCalledExactlyOnceWith("typed");
  });

  it("throws when the save fails for any other reason", async () => {
    for (const status of [400, 413, 422, 500]) {
      stubFetch(reply(status));
      await expect(saveProfileRequest("p", payload, vi.fn()), String(status)).rejects.toThrow("Save failed");
    }
  });

  it("throws when the replacing save fails", async () => {
    stubFetch(reply(409, { detail: { name: "p" } }), reply(500));
    await expect(saveProfileRequest("p", payload, vi.fn().mockResolvedValue(true))).rejects.toThrow("Save failed");
  });

  it("throws when the request never gets there", async () => {
    stubFetch(new TypeError("Failed to fetch"));
    await expect(saveProfileRequest("p", payload, vi.fn())).rejects.toThrow("Failed to fetch");
  });
});

describe("buildProfilePayload", () => {
  const vs = { enabled: true, range: [3, 9] as [number, number], pinned: [4, 5] };

  it("saves every tab's config, in order, and nothing else about the tabs", () => {
    const a = config("A", "time", ["a"]);
    const b = config("B", "time", ["b"]);
    const payload = buildProfilePayload([tab("ta", a), tab("tb", b)], "tb", vs);
    expect(payload.version).toBe(2);
    expect(payload.tabs).toEqual([{ config: a }, { config: b }]);
  });

  it("records which tab is active", () => {
    const tabs = [tab("ta"), tab("tb"), tab("tc")];
    expect(buildProfilePayload(tabs, "tc", vs).activeTabIndex).toBe(2);
    expect(buildProfilePayload(tabs, "ta", vs).activeTabIndex).toBe(0);
  });

  it("falls back to the first tab when the active one is unknown", () => {
    const tabs = [tab("ta"), tab("tb")];
    expect(buildProfilePayload(tabs, null, vs).activeTabIndex).toBe(0);
    expect(buildProfilePayload(tabs, "gone", vs).activeTabIndex).toBe(0);
  });

  it("saves the comparison settings once for the whole profile", () => {
    expect(buildProfilePayload([tab("ta")], "ta", vs)).toMatchObject({
      vsEnabled: true,
      vsRange: [3, 9],
      vsPinned: [4, 5],
    });
  });
});

describe("tabsFromProfile", () => {
  const profile = profileOf([config("A", "time", ["a"]), config("B", "time", [])]);

  it("makes one tab per saved tab, with the saved config", () => {
    const tabs = tabsFromProfile(profile);
    expect(tabs.map((t) => t.config)).toEqual([profile.tabs[0]!.config, profile.tabs[1]!.config]);
  });

  it("gives every tab its own id", () => {
    vi.spyOn(Math, "random").mockReturnValueOnce(0.111).mockReturnValueOnce(0.777);
    const [a, b] = tabsFromProfile(profile);
    expect(a!.id).toMatch(/^t[0-9a-z]+$/);
    expect(a!.id).not.toBe(b!.id);
  });

  it("starts with no data, no fingerprints and no history", () => {
    for (const t of tabsFromProfile(profile)) {
      expect(t).toMatchObject({
        data: null,
        filterFingerprints: {},
        xAxisFilterFingerprint: "[]",
        historyStack: [],
        historyIndex: -1,
      });
    }
  });

  it("treats the loaded configs as saved, so nothing starts out dirty", () => {
    for (const t of tabsFromProfile(profile)) {
      expect(t.savedSnapshot).toBe(JSON.stringify(t.config));
    }
  });

  it("makes no tabs for a profile with none", () => {
    expect(tabsFromProfile(profileOf([]))).toEqual([]);
  });
});

describe("profileActiveIndex", () => {
  const at = (activeTabIndex: number | undefined) =>
    ({ ...profileOf([]), activeTabIndex }) as unknown as PlotProfile;

  it("is the saved index when it is in range", () => {
    expect(profileActiveIndex(at(0), 3)).toBe(0);
    expect(profileActiveIndex(at(2), 3)).toBe(2);
  });

  it("is clamped to the first and last tab", () => {
    expect(profileActiveIndex(at(-3), 3)).toBe(0);
    expect(profileActiveIndex(at(5), 3)).toBe(2);
    expect(profileActiveIndex(at(5), 1)).toBe(0);
  });

  it("is the first tab when none was saved", () => {
    expect(profileActiveIndex(at(undefined), 3)).toBe(0);
  });
});

describe("profileWarnings", () => {
  it("is empty when every column is in the trial", () => {
    const profile = profileOf([config("A", "time", ["body:x", "wing:x"])]);
    expect(profileWarnings(profile, COLUMNS)).toEqual([]);
  });

  it("is empty for a profile with no tabs, or no tabs field", () => {
    expect(profileWarnings(profileOf([]), COLUMNS)).toEqual([]);
    expect(profileWarnings({ version: 2 }, COLUMNS)).toEqual([]);
  });

  it("names the x-axis and each signal the trial lacks, x-axis first", () => {
    const profile = profileOf([config("Arm", "gone:x", ["body:x", "nope", "also"])]);
    expect(profileWarnings(profile, COLUMNS)).toEqual([
      'Arm: x-axis "gone:x"',
      'Arm: "nope"',
      'Arm: "also"',
    ]);
  });

  it("calls an untitled tab tab 1, tab 2 by its position", () => {
    const profile = profileOf([config("", "time", []), config("", "time", ["nope"])]);
    expect(profileWarnings(profile, COLUMNS)).toEqual(['tab 2: "nope"']);
  });

  it("does not check an x-axis with no column", () => {
    expect(profileWarnings(profileOf([config("A", "", [])]), COLUMNS)).toEqual([]);
  });

  it("tolerates a saved config with no y-axes", () => {
    const old = { ...config("A", "time", []), yAxes: undefined } as unknown as PlotConfig;
    expect(profileWarnings(profileOf([old]), COLUMNS)).toEqual([]);
  });

  it("flags a frame whose orientation or position the trial lacks", () => {
    const profile = profileOf([
      config("A", "time", [], ["ghost", null]),
      config("B", "time", [], [null, "ghost"]),
      config("C", "time", [], ["ghost", "wing"]),
    ]);
    expect(profileWarnings(profile, COLUMNS)).toEqual([
      'A: frame "ghost"',
      'B: frame "@ ghost"',
      'C: frame "ghost @ wing"',
    ]);
  });

  it("accepts a frame whose orientation has a :w column and whose position has an :x column", () => {
    const profile = profileOf([
      config("A", "time", [], ["body", null]),
      config("B", "time", [], [null, "wing"]),
      config("C", "time", [], ["q", "body"]),
    ]);
    expect(profileWarnings(profile, COLUMNS)).toEqual([]);
  });

  it("ignores the world frame, even in a trial with no orientation columns", () => {
    expect(profileWarnings(profileOf([config("A", "time", [], [null, null])]), ["time"])).toEqual([]);
  });

  it("flags every column when the trial has none, one line per problem across tabs", () => {
    const profile = profileOf([config("A", "time", ["a"]), config("B", "time", [])]);
    expect(profileWarnings(profile, [])).toEqual(['A: x-axis "time"', 'A: "a"', 'B: x-axis "time"']);
  });

  // unlike profileMissing, which skips Signal Lab outputs because those are
  // checked against the lab itself, the profile list's badge flags them
  it("flags Signal Lab outputs the trial's own columns do not include", () => {
    const profile = profileOf([config("A", "Lab/x/t", ["Lab/x/y"])]);
    expect(profileWarnings(profile, COLUMNS)).toEqual(['A: x-axis "Lab/x/t"', 'A: "Lab/x/y"']);
    expect(profileWarnings(profile, [...COLUMNS, "Lab/x/t", "Lab/x/y"])).toEqual([]);
  });
});

describe("profileMissing", () => {
  it("is empty when every column is in the trial", () => {
    expect(profileMissing(profileOf([config("A", "time", ["body:x"])]), COLUMNS)).toEqual([]);
  });

  it("names the x-axis and each signal the trial lacks", () => {
    const profile = profileOf([config("Arm", "gone:x", ["body:x", "nope"])]);
    expect(profileMissing(profile, COLUMNS)).toEqual(['Arm: x-axis "gone:x"', 'Arm: signal "nope"']);
  });

  it("calls an untitled tab tab 1, tab 2 by its position", () => {
    const profile = profileOf([config("", "time", []), config("", "time", ["nope"])]);
    expect(profileMissing(profile, COLUMNS)).toEqual(['tab 2: signal "nope"']);
  });

  it("does not check an x-axis with no column", () => {
    expect(profileMissing(profileOf([config("A", "", [])]), COLUMNS)).toEqual([]);
  });

  it("tolerates a saved config with no y-axes", () => {
    const old = { ...config("A", "time", []), yAxes: undefined } as unknown as PlotConfig;
    expect(profileMissing(profileOf([old]), COLUMNS)).toEqual([]);
  });

  it("skips Signal Lab outputs, in the x-axis and among the signals", () => {
    const profile = profileOf([config("A", "Lab/x/t", ["Lab/x/y", "nope"])]);
    expect(profileMissing(profile, COLUMNS)).toEqual(['A: signal "nope"']);
  });

  it("flags a frame whose orientation or position the trial lacks", () => {
    const profile = profileOf([
      config("A", "time", [], ["ghost", null]),
      config("B", "time", [], [null, "ghost"]),
      config("C", "time", [], ["ghost", "wing"]),
    ]);
    expect(profileMissing(profile, COLUMNS)).toEqual([
      'A: frame "ghost"',
      'B: frame "@ ghost"',
      'C: frame "ghost @ wing"',
    ]);
  });

  it("accepts a frame the trial can offer, and ignores the world frame", () => {
    const profile = profileOf([
      config("A", "time", [], ["body", null]),
      config("B", "time", [], [null, "wing"]),
      config("C", "time", [], ["q", "body"]),
      config("D", "time", [], [null, null]),
    ]);
    expect(profileMissing(profile, COLUMNS)).toEqual([]);
  });

  it("reports across tabs, in tab order", () => {
    const profile = profileOf([config("A", "time", ["a"]), config("B", "gone", [], ["ghost", null])]);
    expect(profileMissing(profile, COLUMNS)).toEqual([
      'A: signal "a"',
      'B: x-axis "gone"',
      'B: frame "ghost"',
    ]);
  });
});
