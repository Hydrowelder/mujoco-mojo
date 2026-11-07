// the column pickers' search box and quick-filter chips. a search string looks
// like `path/to/thing:suffix`: the part before the first `:` is a "/"-delimited
// path whose levels may each be a `(a|b)` choice, and the part after is a
// suffix choice such as `(x|y)`. the chips read and rewrite that string, and
// the same string is also a (loosely translated) regex over the column names.
// every function here takes the column list and search string explicitly, so
// the component only has to say which list a given picker is searching.

// smartSort's comparator - a module-level Intl.Collator instance, reused
// across every call rather than passing {sensitivity: "base"} straight to
// String.prototype.localeCompare on each pairwise comparison. The two look
// equivalent but aren't: localeCompare with an options object builds a fresh
// collator internally on every single call, while Collator.prototype.compare
// builds it once. For a column-tree toggle this runs an O(n log n) sort
// (getFilteredCols -> smartSort) synchronously on every folder click across
// however many columns are loaded - with the options-object form this was
// slow enough to read as a real delay before the row's own CSS transition
// even started, since the browser can't paint the class change until this
// synchronous sort finishes.
const smartSortCollator = new Intl.Collator(undefined, { sensitivity: "base" });

// sorts `list` in place (and returns it): `time` first wherever it appears,
// then case-insensitive natural order
export function smartSort(list: string[]): string[] {
  return list.sort((a, b) => {
    const aT = a.toLowerCase() === "time";
    const bT = b.toLowerCase() === "time";
    if (aT && !bT) return -1;
    if (!aT && bT) return 1;
    return smartSortCollator.compare(a, b);
  });
}

// the columns of `base` matching `search`, sorted. `*` is a wildcard, a `:`
// (and the `/` before it) may be preceded by anything, and a search that is
// not a valid regex falls back to a plain case-insensitive substring match
export function filterColumns(base: string[], search: string): string[] {
  if (!search) return smartSort([...base]);
  try {
    let pattern = search.replace(/\*/g, ".*").replace(/\/?:/g, ".*:");
    if (pattern.endsWith("/")) pattern = pattern.replace(/\/$/, "\\/?");
    if (pattern.startsWith(":")) pattern = ".*" + pattern;
    if (pattern.toLowerCase() === "time") pattern = "^time$";
    const query = new RegExp(pattern, "i");
    return smartSort(base.filter((c) => query.test(c)));
  } catch {
    return smartSort(
      base.filter((c) => c.toLowerCase().includes(search.toLowerCase())),
    );
  }
}

// the search string after a chip is clicked: `segment` is added to (or, if
// already chosen, removed from) the choices at path level `depth`, or at the
// suffix when `depth` is "suffix". `columns` is every column of the picker,
// used to tell whether the path now names a folder (and so gets a trailing "/")
export function toggleSearchSegment(
  search: string,
  segment: string,
  depth: number | "suffix",
  columns: string[],
): string {
  let [pathPart = "", suffixPart = ""] = search.split(":");

  if (depth === "suffix") {
    const cleanSeg = segment.replace(":", "");
    let items = (suffixPart ?? "")
      .replace(/[()]/g, "")
      .split("|")
      .filter(Boolean);
    items = items.includes(cleanSeg)
      ? items.filter((i) => i !== cleanSeg)
      : [...items, cleanSeg];
    suffixPart =
      items.length > 1 ? `(${items.sort().join("|")})` : (items[0] ?? "");
  } else {
    let parts = (pathPart ?? "").split("/").filter((p) => p !== "");
    const target = parts[depth] ?? "";
    let items = target.replace(/[()]/g, "").split("|").filter(Boolean);
    items = items.includes(segment)
      ? items.filter((i) => i !== segment)
      : [...items, segment];
    if (items.length === 0) {
      parts = parts.slice(0, depth);
    } else {
      parts[depth] =
        items.length === 1
          ? (items[0] ?? "")
          : `(${items.sort().join("|")})`;
    }
    pathPart = parts.join("/");
    if (pathPart && pathPart.toLowerCase() !== "time") {
      const isFolder = columns.some((c) =>
        c.toLowerCase().startsWith(pathPart.toLowerCase() + "/"),
      );
      if (isFolder) pathPart += "/";
    }
  }
  return (pathPart ?? "") + (suffixPart ? ":" + suffixPart : "");
}

// a regex matching the columns whose names start with the path typed so far:
// `/` may be missing from a name, `*` is a wildcard as it is in filterColumns,
// and `(a|b)` is a choice. text that is not a valid regex (an unbalanced
// bracket, say) is matched as written instead of throwing from the chip rows
function pathPrefixRegex(path: string): RegExp {
  try {
    return new RegExp(
      "^" + path.replace(/\*/g, ".*").replace(/\//g, "\\/?"),
      "i",
    );
  } catch {
    const literal = path
      .split("/")
      .map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
      .join("\\/?");
    return new RegExp("^" + literal, "i");
  }
}

// the chips to offer at path level `depth`: that level's name in every column
// consistent with the levels chosen above it, plus anything already chosen
export function searchSegmentsAtDepth(
  base: string[],
  search: string,
  depth: number,
): string[] {
  const pathSearch = search.split(":")[0] ?? "";
  const parts = pathSearch.split("/").filter((p) => p !== "");
  const selected = (parts[depth] ?? "")
    .replace(/[()]/g, "")
    .split("|")
    .filter(Boolean);
  const prefixParts = parts.slice(0, depth);
  const regex = pathPrefixRegex(prefixParts.join("/"));
  const segments = base
    .filter((c) => regex.test(c))
    .map((c) => {
      const p = c.split(":")[0]!.split("/");
      return p[depth] ?? null;
    })
    .filter(Boolean) as string[];
  return smartSort([...new Set([...selected, ...segments])]);
}

// the suffix chips (`:x`, `:y`, ...) to offer for the columns the path part of
// the search matches, plus any suffix already chosen
export function searchAvailableSuffixes(base: string[], search: string): string[] {
  const [pathPart = "", suffixPart = ""] = search.split(":");
  const selected = (suffixPart ?? "")
    .replace(/[()]/g, "")
    .split("|")
    .filter(Boolean)
    .map((s) => ":" + s);
  const pathRegex = pathPrefixRegex(pathPart ?? "");
  const matches = base.filter((c) => pathRegex.test(c));
  const available = matches
    .map((c) => (c.includes(":") ? ":" + c.split(":").pop() : null))
    .filter(Boolean) as string[];
  return smartSort([...new Set([...selected, ...available])]);
}

// whether the chip `seg` is currently chosen at path level `depth` (or in the suffix)
export function isSearchSegmentActive(
  search: string,
  seg: string,
  depth: number | "suffix",
): boolean {
  if (depth === "suffix") {
    const suffixPart = search.split(":")[1] ?? "";
    const items = suffixPart
      .replace(/[()]/g, "")
      .split("|")
      .filter(Boolean);
    return items.includes(seg.replace(":", ""));
  } else {
    const pathPart = search.split(":")[0] ?? "";
    const levels = pathPart.split("/").filter((p) => p !== "");
    const levelContent = levels[depth] ?? "";
    const items = levelContent
      .replace(/[()]/g, "")
      .split("|")
      .filter(Boolean);
    return items.includes(seg);
  }
}

// the path levels that get a row of chips: one per level already chosen, plus
// the next one to choose
export function searchActiveLevels(search: string): number[] {
  const pathOnly = search.split(":")[0] ?? "";
  const parts = pathOnly.split("/").filter((p) => p !== "");
  return Array.from({ length: parts.length + 1 }, (_, i) => i);
}

// the quaternion bases among the columns: each `<base>:w` column names one
export function quatBases(columns: string[]): string[] {
  return columns.filter((c) => c.endsWith(":w")).map((c) => c.replace(":w", ""));
}

// the columns that can be rotated into another frame: the x, y and z
// components of the vectors named in `vectors` (a base such as `Bodies/B/xpos`),
// plus any column `keep` accepts (an enum signal, which is drawn as it is)
export function rotatableColumns(
  columns: string[],
  vectors: string[],
  keep: (col: string) => boolean = () => false,
): string[] {
  return columns.filter((col) => {
    const parts = col.split(":");
    const suffix = parts.pop();
    const family = parts.join(":");
    return (["x", "y", "z"].includes(suffix ?? "") && vectors.includes(family)) || keep(col);
  });
}
