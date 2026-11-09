// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { COPIED_MS, addCopyButton } from "./code-block";

let block: HTMLElement;

beforeEach(() => {
  vi.useFakeTimers();
  block = document.createElement("div");
  document.body.appendChild(block);
});

afterEach(() => {
  vi.useRealTimers();
  block.remove();
});

// lets the promise the click waits on settle
const settle = () => vi.advanceTimersByTimeAsync(0);

describe("addCopyButton", () => {
  it("adds a button to the block and returns it", () => {
    const button = addCopyButton(block, "ls", () => Promise.resolve(true));

    expect(block.querySelector("button")).toBe(button);
    expect(button.parentElement).toBe(block);
  });

  it("is a plain button that says what it does", () => {
    const button = addCopyButton(block, "ls", () => Promise.resolve(true));

    expect(button.type).toBe("button");
    expect(button.title).toBe("Copy code");
    expect(button.getAttribute("aria-label")).toBe("Copy code");
    expect(button.querySelector("svg")).not.toBeNull();
    expect(button.dataset["copied"]).toBeUndefined();
  });

  it("copies the code of its block, exactly", async () => {
    const copy = vi.fn(() => Promise.resolve(true));
    const code = "mujoco-mojo run monte-carlo \\\n  -g sim.generate\n";
    const button = addCopyButton(block, code, copy);

    button.click();
    await settle();

    expect(copy).toHaveBeenCalledOnce();
    expect(copy).toHaveBeenCalledWith(code);
  });

  it("shows a check mark after a copy that worked, then goes back", async () => {
    const button = addCopyButton(block, "ls", () => Promise.resolve(true));
    const copyIcon = button.innerHTML;

    button.click();
    await settle();
    expect(button.dataset["copied"]).toBe("true");
    expect(button.title).toBe("Copied");
    expect(button.innerHTML).not.toBe(copyIcon);

    await vi.advanceTimersByTimeAsync(COPIED_MS - 1);
    expect(button.dataset["copied"]).toBe("true");
    await vi.advanceTimersByTimeAsync(1);
    expect(button.dataset["copied"]).toBeUndefined();
    expect(button.title).toBe("Copy code");
    expect(button.innerHTML).toBe(copyIcon);
  });

  it("is left alone after a copy that failed", async () => {
    const button = addCopyButton(block, "ls", () => Promise.resolve(false));
    const before = button.innerHTML;

    button.click();
    await settle();

    expect(button.dataset["copied"]).toBeUndefined();
    expect(button.innerHTML).toBe(before);
    expect(button.title).toBe("Copy code");
  });

  it("keeps the check mark for a full moment after a second click", async () => {
    const button = addCopyButton(block, "ls", () => Promise.resolve(true));

    button.click();
    await settle();
    await vi.advanceTimersByTimeAsync(COPIED_MS - 500);
    button.click();
    await settle();
    await vi.advanceTimersByTimeAsync(COPIED_MS - 1);

    expect(button.dataset["copied"]).toBe("true");
    await vi.advanceTimersByTimeAsync(1);
    expect(button.dataset["copied"]).toBeUndefined();
  });

  it("copies again on every click", async () => {
    const copy = vi.fn(() => Promise.resolve(true));
    const button = addCopyButton(block, "ls", copy);

    button.click();
    await settle();
    await vi.advanceTimersByTimeAsync(COPIED_MS);
    button.click();
    await settle();

    expect(copy).toHaveBeenCalledTimes(2);
  });

  it("gives each block its own button and its own code", async () => {
    const other = document.createElement("div");
    document.body.appendChild(other);
    const copy = vi.fn(() => Promise.resolve(true));
    const first = addCopyButton(block, "one", copy);
    const second = addCopyButton(other, "two", copy);

    second.click();
    await settle();

    expect(copy).toHaveBeenCalledWith("two");
    expect(first.dataset["copied"]).toBeUndefined();
    expect(second.dataset["copied"]).toBe("true");
    other.remove();
  });
});
