// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createSettingsPanelState,
  type SettingsGetResponse,
  type SettingsPanelState,
  type SettingsSchema,
} from "./settings-panel";

// the panel's store slice: loading, editing and saving the settings. the
// schema walking and serialization it leans on are covered in
// settings-panel.test.ts; this is about the state and the requests

const schema: SettingsSchema = {
  type: "object",
  properties: { general: { $ref: "#/$defs/General" }, dojo: { $ref: "#/$defs/Dojo" } },
  $defs: {
    General: {
      type: "object",
      title: "General",
      properties: {
        verbose: { type: "integer", title: "Verbosity", minimum: 0, maximum: 3, default: 0 },
        chime: { anyOf: [{ type: "string", format: "uri" }, { type: "null" }], title: "Chime" },
        debug: { type: "boolean", default: false },
      },
    },
    Dojo: {
      type: "object",
      title: "Dojo",
      properties: {
        show_quick_filters: { type: "boolean", default: true },
        models: { type: "array", title: "Models", items: { $ref: "#/$defs/ModelEntry" } },
        tags: { type: "object", title: "Tags", additionalProperties: { type: "string" } },
      },
    },
    ModelEntry: {
      type: "object",
      title: "Model",
      properties: {
        name: { type: "string" },
        kind: { type: "string", enum: ["a", "b"] },
        on: { type: "boolean" },
        n: { type: "integer", minimum: 2 },
      },
    },
  },
};

const values = () => ({
  general: { verbose: 1, chime: "https://x.test/a.mp3", debug: false },
  dojo: { show_quick_filters: false, models: [{ name: "gpt", kind: "b", on: true, n: 5 }], tags: { a: "1" } },
});

const response = (over: Partial<SettingsGetResponse> = {}): SettingsGetResponse => ({
  schema,
  values: values(),
  value_meta: { "general.chime": { is_url: true } },
  color_choices: { RED: "#ff0000" },
  is_localhost: true,
  ...over,
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

let fetchMock: ReturnType<typeof vi.fn>;
let toast: ReturnType<typeof vi.fn>;
let state: SettingsPanelState;

const fieldOf = (path: string) => {
  for (const g of state.settingsSections) {
    const f = g.fields.find((x) => x.path === path);
    if (f) return f;
  }
  throw new Error(`no field ${path}`);
};

// a state that has loaded the settings, as it is once the panel has opened
async function loadedState() {
  fetchMock.mockResolvedValueOnce(json(response()));
  await state.openSettings();
  fetchMock.mockClear();
}

beforeEach(() => {
  localStorage.clear();
  document.body.style.overflow = "";
  fetchMock = vi.fn();
  toast = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("Alpine", { store: () => ({ toast }) });
  state = createSettingsPanelState();
});

afterEach(() => {
  vi.unstubAllGlobals();
  delete (window as unknown as Record<string, unknown>).mojoConfirm;
});

describe("initial state", () => {
  it("starts closed and empty", () => {
    expect(state).toMatchObject({
      settingsOpen: false,
      settingsLoading: false,
      settingsSaving: false,
      settingsError: "",
      settingsSections: [],
      settingsSearchQuery: "",
      settingsHintText: "",
    });
    expect(state.settingsActiveGroup()).toBeNull();
  });

  it("restores which sections were collapsed and which one was open", () => {
    localStorage.setItem("mojo:settings:collapsed-sections", JSON.stringify({ "general.nested": true }));
    localStorage.setItem("mojo:settings:active-section", "dojo");
    const restored = createSettingsPanelState();
    expect(restored.settingsCollapsed).toEqual({ "general.nested": true });
    expect(restored.settingsActiveSectionPath).toBe("dojo");
  });

  it("ignores stored text that is not valid", () => {
    localStorage.setItem("mojo:settings:collapsed-sections", "not json");
    expect(createSettingsPanelState().settingsCollapsed).toEqual({});
  });
});

describe("openSettings", () => {
  it("opens, locks page scrolling, loads and parses the settings", async () => {
    fetchMock.mockResolvedValueOnce(json(response()));
    await state.openSettings();
    expect(fetchMock).toHaveBeenCalledWith("/settings");
    expect(state).toMatchObject({
      settingsOpen: true,
      settingsLoading: false,
      settingsError: "",
      settingsIsLocalhost: true,
      settingsColorChoices: { RED: "#ff0000" },
    });
    expect(document.body.style.overflow).toBe("hidden");
    expect(state.settingsSections.map((g) => g.key)).toEqual(["general", "dojo"]);
    expect(fieldOf("general.verbose").value).toBe(1);
  });

  it("takes the quick-filters preference from the loaded values", async () => {
    expect(state.showQuickFilters).toBeUndefined();
    await loadedState();
    expect(state.showQuickFilters).toBe(false);
  });

  it("is still loading while the request is out", async () => {
    let release!: (r: Response) => void;
    fetchMock.mockReturnValueOnce(new Promise<Response>((resolve) => (release = resolve)));
    const pending = state.openSettings();
    expect(state.settingsLoading).toBe(true);
    release(json(response()));
    await pending;
    expect(state.settingsLoading).toBe(false);
  });

  it.each([
    ["a message", { detail: "Not allowed from here." }, "Not allowed from here."],
    [
      "a list of validation errors",
      { detail: [{ msg: "value must be >= 0" }, { msg: "unknown field" }] },
      "value must be >= 0; unknown field",
    ],
    ["a body with no detail", {}, "Request failed (500)"],
  ])("shows the server's error when it answers with %s", async (_label, body, message) => {
    fetchMock.mockResolvedValueOnce(json(body, 500));
    await state.openSettings();
    expect(state.settingsError).toBe(message);
    expect(state.settingsLoading).toBe(false);
  });

  it("falls back to the status for an error that is not JSON", async () => {
    fetchMock.mockResolvedValueOnce(new Response("<html>oops</html>", { status: 502 }));
    await state.openSettings();
    expect(state.settingsError).toBe("Request failed (502)");
  });

  it("shows a network failure's message", async () => {
    fetchMock.mockRejectedValueOnce(new Error("connection refused"));
    await state.openSettings();
    expect(state.settingsError).toBe("connection refused");
    expect(state.settingsLoading).toBe(false);
  });
});

describe("closeSettings and the hint bar", () => {
  it("closes, frees page scrolling and clears the search and hint", async () => {
    await loadedState();
    state.settingsSearchQuery = "verb";
    state.showSettingsHint("Some help");
    state.closeSettings();
    expect(state).toMatchObject({ settingsOpen: false, settingsSearchQuery: "", settingsHintText: "" });
    expect(document.body.style.overflow).toBe("");
  });

  it("shows a hint only while the panel is open", async () => {
    state.showSettingsHint("ignored while closed");
    expect(state.settingsHintText).toBe("");
    await loadedState();
    state.showSettingsHint("Some help");
    expect(state.settingsHintText).toBe("Some help");
    state.hideSettingsHint();
    expect(state.settingsHintText).toBe("");
  });

  it("does not let a hover that lands during the closing fade bring the hint back", async () => {
    await loadedState();
    state.closeSettings();
    state.showSettingsHint("late hover");
    expect(state.settingsHintText).toBe("");
  });
});

describe("editing fields", () => {
  beforeEach(loadedState);

  it("sets a field's value by path", () => {
    state.updateField("general.verbose", 3);
    expect(fieldOf("general.verbose").value).toBe(3);
  });

  it("ignores a path that matches no field", () => {
    expect(() => state.updateField("general.nope", 1)).not.toThrow();
  });

  it("re-checks whether a url field's value is a url as it is edited", () => {
    expect(fieldOf("general.chime").isUrl).toBe(true);
    state.updateField("general.chime", "/home/me/chime.mp3");
    expect(fieldOf("general.chime").isUrl).toBe(false);
    state.updateField("general.chime", "https://example.com/a.mp3");
    expect(fieldOf("general.chime").isUrl).toBe(true);
  });

  it("resets one field to its default", () => {
    state.updateField("general.verbose", 3);
    state.resetField("general.verbose");
    expect(fieldOf("general.verbose").value).toBe(0);
    state.resetField("general.chime");
    expect(fieldOf("general.chime")).toMatchObject({ value: null, isUrl: false });
  });

  it("reports out-of-range numbers and blocks nothing until asked to", () => {
    expect(state.settingsHasInvalidFields()).toBe(false);
    state.updateField("general.verbose", 9);
    expect(state.settingsHasInvalidFields()).toBe(true);
    expect(state.settingsFieldOutOfRange(fieldOf("general.verbose"))).toBe(true);
    expect(state.settingsFieldRangeMessage(fieldOf("general.verbose"))).toBe("Must be between 0 and 3");
  });
});

describe("saveSettings", () => {
  beforeEach(loadedState);

  it("refuses to save while a field is out of range", async () => {
    state.updateField("general.verbose", 9);
    await state.saveSettings();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(state.settingsError).toBe("Fix the highlighted field(s) before saving.");
    expect(state.settingsSaving).toBe(false);
  });

  it("posts the edited settings as JSON, applies the answer and says it saved", async () => {
    state.updateField("general.verbose", 2);
    const saved = values();
    saved.general.verbose = 2;
    fetchMock.mockResolvedValueOnce(json({ values: saved, value_meta: {} }));
    await state.saveSettings();

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/settings");
    expect(init).toMatchObject({ method: "POST", headers: { "Content-Type": "application/json" } });
    expect(JSON.parse(init.body)).toMatchObject({ general: { verbose: 2, debug: false } });
    expect(toast).toHaveBeenCalledWith("Settings saved", "success");
    expect(state.settingsSaving).toBe(false);
    expect(state.settingsError).toBe("");
  });

  it("announces the save to the rest of the page", async () => {
    const heard: unknown[] = [];
    const listener = (e: Event) => heard.push((e as CustomEvent).detail);
    window.addEventListener("mojo-settings-saved", listener);
    fetchMock.mockResolvedValueOnce(json({ values: values(), value_meta: {} }));
    await state.saveSettings();
    window.removeEventListener("mojo-settings-saved", listener);
    expect(heard).toEqual([values()]);
  });

  it("updates the quick-filters preference from what the server stored", async () => {
    const saved = values();
    saved.dojo.show_quick_filters = true;
    fetchMock.mockResolvedValueOnce(json({ values: saved, value_meta: {} }));
    await state.saveSettings();
    expect(state.showQuickFilters).toBe(true);
  });

  it("shows the server's rejection both in the panel and as a toast", async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: "Port must be free." }, 422));
    await state.saveSettings();
    expect(state.settingsError).toBe("Port must be free.");
    expect(toast).toHaveBeenCalledWith("Port must be free.", "error");
    expect(state.settingsSaving).toBe(false);
  });

  it("reports a network failure the same way", async () => {
    fetchMock.mockRejectedValueOnce(new Error("offline"));
    await state.saveSettings();
    expect(state.settingsError).toBe("offline");
    expect(toast).toHaveBeenCalledWith("offline", "error");
  });
});

describe("resetAllToDefaults", () => {
  beforeEach(loadedState);

  it("does nothing unless the user confirms", async () => {
    (window as unknown as Record<string, unknown>).mojoConfirm = vi.fn().mockResolvedValue(false);
    await state.resetAllToDefaults();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does nothing when there is no confirm dialog to ask with", async () => {
    await state.resetAllToDefaults();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("posts the reset, applies the defaults it gets back and says so", async () => {
    const confirm = vi.fn().mockResolvedValue(true);
    (window as unknown as Record<string, unknown>).mojoConfirm = confirm;
    const defaults = values();
    defaults.general.verbose = 0;
    fetchMock.mockResolvedValueOnce(json({ values: defaults, value_meta: {} }));
    await state.resetAllToDefaults();

    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ variant: "danger" }));
    expect(fetchMock).toHaveBeenCalledWith("/settings/reset", { method: "POST" });
    expect(fieldOf("general.verbose").value).toBe(0);
    expect(toast).toHaveBeenCalledWith("Settings restored to defaults", "success");
    expect(state.settingsSaving).toBe(false);
  });

  it("toasts the failure", async () => {
    (window as unknown as Record<string, unknown>).mojoConfirm = vi.fn().mockResolvedValue(true);
    fetchMock.mockResolvedValueOnce(json({ detail: "Read-only." }, 403));
    await state.resetAllToDefaults();
    expect(toast).toHaveBeenCalledWith("Read-only.", "error");
    expect(state.settingsSaving).toBe(false);
  });
});

describe("applying a write before the settings were ever loaded", () => {
  it("does nothing, and announces nothing", () => {
    const heard = vi.fn();
    window.addEventListener("mojo-settings-saved", heard);
    state._applySettingsWrite({ values: values(), value_meta: {} });
    window.removeEventListener("mojo-settings-saved", heard);
    expect(state.settingsSections).toEqual([]);
    expect(heard).not.toHaveBeenCalled();
  });
});

describe("sections", () => {
  beforeEach(loadedState);

  it("falls back to the first section when none, or a stale one, is selected", () => {
    expect(state.settingsActiveGroup()?.key).toBe("general");
    state.settingsActiveSectionPath = "removed-section";
    expect(state.settingsActiveGroup()?.key).toBe("general");
    state.settingsActiveSectionPath = "dojo";
    expect(state.settingsActiveGroup()?.key).toBe("dojo");
  });

  it("selecting one clears the search and remembers the choice", () => {
    state.settingsSearchQuery = "verb";
    state.selectSettingsSection("dojo");
    expect(state).toMatchObject({ settingsActiveSectionPath: "dojo", settingsSearchQuery: "" });
    expect(localStorage.getItem("mojo:settings:active-section")).toBe("dojo");
  });

  it("toggling collapses and expands a section and remembers it", () => {
    state.toggleSettingsSection("general");
    expect(state.settingsCollapsed).toEqual({ general: true });
    state.toggleSettingsSection("general");
    expect(state.settingsCollapsed).toEqual({ general: false });
    expect(JSON.parse(localStorage.getItem("mojo:settings:collapsed-sections")!)).toEqual({ general: false });
  });

  it("filters by the search query without touching the sections", () => {
    state.settingsSearchQuery = "verbosity";
    expect(state.settingsFilteredSections().map((g) => g.key)).toEqual(["general"]);
    expect(state.settingsSections).toHaveLength(2);
    state.settingsSearchQuery = "";
    expect(state.settingsFilteredSections()).toBe(state.settingsSections);
  });
});

describe("dict entries and list rows", () => {
  beforeEach(loadedState);

  it("adds a blank string entry to a dict and removes one by index", () => {
    state.addDictEntry("dojo");
    const dict = () => state.settingsSections[1]!.dictField!.entries;
    expect(dict()).toEqual([
      { key: "a", valueType: "string", value: "1" },
      { key: "", valueType: "string", value: "" },
    ]);
    state.removeDictEntry("dojo", 0);
    expect(dict()).toEqual([{ key: "", valueType: "string", value: "" }]);
  });

  it("ignores a dict path that has no dict", () => {
    expect(() => state.addDictEntry("general")).not.toThrow();
    expect(() => state.removeDictEntry("nope", 0)).not.toThrow();
  });

  it("adds a list row that starts on a sensible value for each kind of field", () => {
    state.addListItem("dojo.models");
    const rows = state.settingsSections[1]!.listFields[0]!.items;
    expect(rows).toHaveLength(2);
    const added = Object.fromEntries(rows[1]!.fields.map((f) => [f.key, f.value]));
    expect(added).toEqual({ name: "", kind: "a", on: false, n: 2 });
  });

  it("gives each added row its own field paths", () => {
    state.addListItem("dojo.models");
    state.addListItem("dojo.models");
    const paths = state.settingsSections[1]!.listFields[0]!.items.flatMap((r) => r.fields.map((f) => f.path));
    expect(new Set(paths).size).toBe(paths.length);
  });

  it("removes a list row by index", () => {
    state.removeListItem("dojo.models", 0);
    expect(state.settingsSections[1]!.listFields[0]!.items).toEqual([]);
  });

  it("includes added rows in what gets saved", async () => {
    state.addListItem("dojo.models");
    fetchMock.mockResolvedValueOnce(json({ values: values(), value_meta: {} }));
    await state.saveSettings();
    const body = JSON.parse(fetchMock.mock.calls[0]![1].body) as ReturnType<typeof values>;
    expect(body.dojo.models).toEqual([
      { name: "gpt", kind: "b", on: true, n: 5 },
      { name: "", kind: "a", on: false, n: 2 },
    ]);
  });
});

describe("openOnLocalhost", () => {
  it("reopens the current page on 127.0.0.1 in a new tab", () => {
    const open = vi.fn();
    vi.stubGlobal("open", open);
    (window as unknown as { happyDOM: { setURL(url: string): void } }).happyDOM.setURL("http://192.168.1.5:8000/monitor");
    state.openOnLocalhost();
    expect(open).toHaveBeenCalledWith("http://127.0.0.1:8000/monitor", "_blank", "noopener");
  });
});

describe("renderMarkdown", () => {
  it("renders markdown to HTML", () => {
    expect(state.renderMarkdown("**bold** and `code`")).toContain("<strong>bold</strong>");
    expect(state.renderMarkdown("**bold** and `code`")).toContain("<code>code</code>");
  });
});
