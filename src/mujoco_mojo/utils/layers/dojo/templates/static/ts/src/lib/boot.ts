// small rules from the trial viewer's page load, moved out of trial-viewer.ts
// so they can be tested without booting a page.

// the zero-padding width in a job's padding style such as `trial_{:03d}`: the
// first number in it, or 2 when it has none
export function paddingLength(paddingStyle: string): number {
  const match = paddingStyle.match(/\d+/);
  return match ? parseInt(match[0]!) : 2;
}

// what to do with a `?v=` shared link in the address bar. A link left there
// survives a plain page refresh, so without asking first every such refresh
// would silently replace the plot tabs already saved in this browser; ask only
// when there is something to lose.
export function sharedLinkDecision(
  shared: string | null,
  hasStoredTabs: boolean,
): "none" | "use" | "ask" {
  if (!shared) return "none";
  return hasStoredTabs ? "ask" : "use";
}

// the address without its `?v=` parameter, so a later refresh does not ask
// again (or silently reapply it) for a link that has been handled once
export function withoutSharedParam(href: string): string {
  const url = new URL(href);
  url.searchParams.delete("v");
  return url.toString();
}
