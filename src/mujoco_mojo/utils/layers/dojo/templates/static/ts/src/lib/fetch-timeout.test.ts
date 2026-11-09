import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { fetchWithRetry, fetchWithTimeout } from "./fetch-timeout";

type FetchArgs = [input: RequestInfo | URL, init?: RequestInit];
type FetchFn = (...args: FetchArgs) => Promise<Response>;

// a fetch that never answers but rejects the way a real one does when aborted
function hangUntilAborted(...[, init]: FetchArgs): Promise<Response> {
  return new Promise((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  });
}

const ok = (status = 200) => new Response("body", { status });

let fetchMock: Mock<FetchFn>;

beforeEach(() => {
  vi.useFakeTimers();
  fetchMock = vi.fn<FetchFn>();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("fetchWithTimeout", () => {
  it("passes the input and init through, adding an abort signal", async () => {
    fetchMock.mockResolvedValue(ok());
    await fetchWithTimeout("/x", { method: "POST", body: "b" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/x",
      expect.objectContaining({ method: "POST", body: "b", signal: expect.any(AbortSignal) }),
    );
  });

  it("resolves with the response and leaves no timer behind", async () => {
    const response = ok(201);
    fetchMock.mockResolvedValue(response);
    await expect(fetchWithTimeout("/x")).resolves.toBe(response);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("clears its timer when the fetch rejects too", async () => {
    fetchMock.mockRejectedValue(new Error("connection refused"));
    await expect(fetchWithTimeout("/x")).rejects.toThrow("connection refused");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("aborts a request that outlives the timeout", async () => {
    let signal: AbortSignal | undefined;
    fetchMock.mockImplementation((...args) => {
      signal = args[1]?.signal ?? undefined;
      return hangUntilAborted(...args);
    });
    const settled = expect(fetchWithTimeout("/x", {}, 5000)).rejects.toMatchObject({ name: "AbortError" });
    await vi.advanceTimersByTimeAsync(4999);
    expect(signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(signal?.aborted).toBe(true);
    await settled;
  });

  it("defaults to a thirty second timeout", async () => {
    let signal: AbortSignal | undefined;
    fetchMock.mockImplementation((...args) => {
      signal = args[1]?.signal ?? undefined;
      return hangUntilAborted(...args);
    });
    const settled = expect(fetchWithTimeout("/x")).rejects.toMatchObject({ name: "AbortError" });
    await vi.advanceTimersByTimeAsync(29_999);
    expect(signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(signal?.aborted).toBe(true);
    await settled;
  });
});

describe("fetchWithRetry", () => {
  it("returns the first response without waiting", async () => {
    const response = ok();
    fetchMock.mockResolvedValue(response);
    await expect(fetchWithRetry("/x")).resolves.toBe(response);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("retries a rejected fetch after the retry delay until one succeeds", async () => {
    const response = ok();
    fetchMock
      .mockRejectedValueOnce(new Error("refused"))
      .mockRejectedValueOnce(new Error("refused"))
      .mockResolvedValueOnce(response);
    const result = fetchWithRetry("/x", {}, { retryDelayMs: 1000 });

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(999);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1000);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    await expect(result).resolves.toBe(response);
  });

  it("does not retry an HTTP error, since the server answered", async () => {
    const unavailable = ok(503);
    fetchMock.mockResolvedValue(unavailable);
    await expect(fetchWithRetry("/x")).resolves.toBe(unavailable);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("gives up after the maximum attempts and throws the last error", async () => {
    fetchMock.mockRejectedValue(new Error("down"));
    const settled = expect(fetchWithRetry("/x", {}, { maxAttempts: 3, retryDelayMs: 10 })).rejects.toThrow("down");
    await vi.advanceTimersByTimeAsync(100);
    await settled;
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("retries a request that timed out", async () => {
    const response = ok();
    fetchMock.mockImplementationOnce(hangUntilAborted).mockResolvedValueOnce(response);
    const result = fetchWithRetry("/x", {}, { timeoutMs: 100, retryDelayMs: 50 });

    await vi.advanceTimersByTimeAsync(100);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(50);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await expect(result).resolves.toBe(response);
  });
});
