import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createToastMixin } from "./toast";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("createToastMixin", () => {
  it("starts hidden with a success type", () => {
    expect(createToastMixin()).toMatchObject({ showToast: false, toastMessage: "", toastType: "success" });
  });

  it("shows the message and hides it again after three seconds", () => {
    const toast = createToastMixin();
    toast.notify("Saved");
    expect(toast).toMatchObject({ showToast: true, toastMessage: "Saved", toastType: "success" });
    vi.advanceTimersByTime(2999);
    expect(toast.showToast).toBe(true);
    vi.advanceTimersByTime(1);
    expect(toast.showToast).toBe(false);
  });

  it("takes the type it is given", () => {
    const toast = createToastMixin();
    toast.notify("Nope", "error");
    expect(toast.toastType).toBe("error");
  });

  it("replaces the message of a toast that is already showing", () => {
    const toast = createToastMixin();
    toast.notify("one");
    toast.notify("two", "info");
    expect(toast).toMatchObject({ toastMessage: "two", toastType: "info", showToast: true });
  });

  it("copies the message into the global notification history when the store is ready", () => {
    const addNotification = vi.fn();
    vi.stubGlobal("Alpine", { store: () => ({ addNotification }) });
    createToastMixin().notify("Saved", "info");
    expect(addNotification).toHaveBeenCalledWith("Saved", "info");
  });

  it("still shows the toast when the store has no addNotification", () => {
    vi.stubGlobal("Alpine", { store: () => ({}) });
    const toast = createToastMixin();
    expect(() => toast.notify("Saved")).not.toThrow();
    expect(toast.showToast).toBe(true);
  });

  it("still shows the toast when Alpine is missing or its store throws", () => {
    const toast = createToastMixin();
    expect(() => toast.notify("before Alpine exists")).not.toThrow();
    expect(toast.showToast).toBe(true);

    vi.stubGlobal("Alpine", {
      store: () => {
        throw new Error("store not registered");
      },
    });
    const second = createToastMixin();
    expect(() => second.notify("store throws")).not.toThrow();
    expect(second.showToast).toBe(true);
  });
});
