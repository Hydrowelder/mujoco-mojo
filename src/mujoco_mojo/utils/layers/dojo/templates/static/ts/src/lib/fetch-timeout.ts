// Wraps fetch() with a hard timeout via AbortController, so a request that
// hangs rather than cleanly erroring - e.g. mid-flight when the Dojo server
// process is restarting/disconnecting - still eventually rejects instead of
// stalling forever. A plain fetch() to a server that's already down usually
// rejects quickly (connection refused), but one to a server that dies
// mid-request with no timeout of its own can hang indefinitely: nothing
// else in that call chain would ever throw, so a try/finally built around
// it (e.g. each page's own init(), which flips the global loading screen
// off in its finally block) never reaches its finally either, leaving the
// loading screen stuck on. Mirrors the AbortController + setTimeout pattern
// store.ts's checkServerHealth() already uses for its own health-check
// fetch, generalized here for reuse at every other fetch that gates page
// load.
export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = 30000,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

// A different, pre-existing failure mode from the one above: refreshing (or
// first loading) the page while the Dojo server is still starting up (not
// yet listening on its port) doesn't hang - it fails immediately with a
// connection-refused-style rejection - so fetchWithTimeout alone doesn't
// help there, and the caller's own try/catch just gives up on the first
// attempt, leaving the page stuck on its initial error/loading state with
// no path to recovery short of a manual reload. This retries on exactly
// that failure mode (fetch() rejecting - network/connection-level, not a
// clean non-ok HTTP response, which means the server IS up and answering,
// just with an error worth surfacing rather than retrying blindly), waiting
// retryDelayMs between attempts, so a page opened a few seconds before the
// server finishes starting recovers on its own once it's ready. Capped at
// maxAttempts (default 30 * 10s = 5 minutes) rather than retrying forever,
// so a genuinely broken server still falls through to the normal error
// state instead of leaving the loading screen spinning indefinitely.
export async function fetchWithRetry(
  input: RequestInfo | URL,
  init: RequestInit = {},
  { timeoutMs = 30000, retryDelayMs = 10000, maxAttempts = 30 } = {},
): Promise<Response> {
  for (let attempt = 1; ; attempt += 1) {
    try {
      return await fetchWithTimeout(input, init, timeoutMs);
    } catch (e) {
      if (attempt >= maxAttempts) throw e;
      await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
    }
  }
}
