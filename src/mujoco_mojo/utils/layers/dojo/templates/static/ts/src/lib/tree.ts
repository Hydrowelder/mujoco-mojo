// Generic folder/file tree built from a flat list of items keyed by a
// "/"-delimited `name` string - the convention shared by saved plot-config
// Profiles (_chart.html) and Signal Lab configs (_signal_lab.html), both of
// which let a user organize entries into "folder/sub/name"-style paths with
// no real folder entity anywhere (server or client): a "folder" only exists
// for as long as at least one file's name happens to start with that
// prefix. Both UIs are built on this one module rather than each growing
// its own copy, matching this codebase's established pattern (e.g.
// settings-panel.ts's schema walk) of centralizing a shape shared by more
// than one screen.
//
// Rendered as a single flat, depth-annotated row list, not nested Alpine
// templates: Alpine has no first-class recursive-component system the way
// Vue/React do, so hand-nesting <template x-for> only works up to however
// many levels you're willing to write out by hand (the settings panel's own
// two-level section/subgroup markup is exactly that kind of cap). Flattening
// sidesteps the problem entirely and scales to any depth for free - it's
// also how virtualized tree views, including VS Code's own explorer,
// already work internally.

export interface TreeRow<T> {
  type: "folder" | "file";
  /** Full path: "a/b" for a folder, "a/b/c" (== the source item's `name`) for a file. */
  path: string;
  /** Last path segment only, for display - "b" or "c" above. */
  name: string;
  /** 0-based indentation level. */
  depth: number;
  /** The original item, present only when `type === "file"`. */
  item: T | null;
  /** Total files under this node: 1 for a file, a recursive count for a folder - for a count badge. */
  fileCount: number;
  /**
   * Unique key for Alpine's `:key` binding - `"folder:a/b"` / `"file:a/b"`,
   * not just `path` on its own. A leaf's bare name can legitimately equal a
   * sibling folder's name (e.g. a scalar signal named "body" alongside a
   * "body/x" sub-signal), which would otherwise give a folder row and a
   * file row the same `path` and the same Alpine key - x-for silently
   * conflates same-keyed nodes, which showed up as the file disappearing
   * whenever its same-named folder was toggled.
   */
  key: string;
  /**
   * Whether this row should currently render as collapsed-away. `visibleTreeRows`
   * ANNOTATES every row with this rather than filtering the array down to a
   * shorter one - Alpine's `x-for` has no transition support at all for
   * array insertions/removals (confirmed straight from its source: a
   * removed item is synchronously `destroyTree()`'d and `.remove()`'d, with
   * no hook for a leave animation), so an item that's actually removed
   * from the array can only ever snap away instantly. Keeping every row
   * permanently present and toggling this flag instead means the DOM node
   * never goes away - visibility becomes a `:class` toggle on a persistent
   * element, which is what lets a real CSS transition (the same
   * .expander-body-wrap grid trick used elsewhere in this codebase) work
   * at all.
   */
  hidden: boolean;
}

interface FolderNode<T> {
  path: string;
  folders: Map<string, FolderNode<T>>;
  files: Array<{ name: string; item: T }>;
}

function insert<T extends { name: string }>(root: FolderNode<T>, item: T): void {
  // ":"-suffixed attributes (e.g. "body/joint:ke_rot", the same convention
  // getAvailableSuffixes/toggleRegexSegment's "suffix" depth already treats
  // specially) nest as one more path segment under their base, rather than
  // being folded into a single opaque leaf name - "joint" becomes a real
  // folder and "ke_rot" a leaf under it, not a leaf literally named
  // "joint:ke_rot". Only the first ":" counts as this separator; harmless
  // no-op for names that never contain one (profiles/labs never do).
  const colonIdx = item.name.indexOf(":");
  const pathPart = colonIdx === -1 ? item.name : item.name.slice(0, colonIdx);
  const attrPart = colonIdx === -1 ? null : item.name.slice(colonIdx + 1);
  const segments = pathPart.split("/").filter((s) => s.length > 0);
  if (attrPart) segments.push(attrPart);
  if (segments.length === 0) return;
  let node = root;
  for (let i = 0; i < segments.length - 1; i++) {
    const seg = segments[i];
    const path = node.path ? `${node.path}/${seg}` : seg;
    let child = node.folders.get(seg);
    if (!child) {
      child = { path, folders: new Map(), files: [] };
      node.folders.set(seg, child);
    }
    node = child;
  }
  node.files.push({ name: segments[segments.length - 1], item });
}

function pushFile<T>(node: FolderNode<T>, f: { name: string; item: T }, depth: number, out: TreeRow<T>[]): void {
  const path = node.path ? `${node.path}/${f.name}` : f.name;
  out.push({ type: "file", path, name: f.name, depth, item: f.item, fileCount: 1, key: `file:${path}`, hidden: false });
}

function flatten<T>(node: FolderNode<T>, depth: number, out: TreeRow<T>[]): number {
  let fileCount = 0;
  // folders alphabetical and always before files at the same level, files
  // keep whatever order the caller gave them (e.g. already sorted by
  // recency) - the same default policy VS Code's own explorer uses.
  const folderNames = [...node.folders.keys()].sort((a, b) => a.localeCompare(b));

  // "time", when present as a direct file at this level, sorts before
  // everything else at this level - folders included - matching
  // getFilteredCols's own smartSort() convention of always surfacing time
  // first wherever it appears in a signal list.
  const timeIdx = node.files.findIndex((f) => f.name.toLowerCase() === "time");
  if (timeIdx !== -1) {
    pushFile(node, node.files[timeIdx]!, depth, out);
    fileCount += 1;
  }

  for (const name of folderNames) {
    const child = node.folders.get(name);
    if (!child) continue;
    const row: TreeRow<T> = {
      type: "folder",
      path: child.path,
      name,
      depth,
      item: null,
      fileCount: 0,
      key: `folder:${child.path}`,
      hidden: false,
    };
    out.push(row);
    row.fileCount = flatten(child, depth + 1, out);
    fileCount += row.fileCount;
  }
  for (let i = 0; i < node.files.length; i++) {
    if (i === timeIdx) continue;
    pushFile(node, node.files[i]!, depth, out);
    fileCount += 1;
  }
  return fileCount;
}

/** Builds a flat, depth-annotated row list from a flat array of items whose `name` is a "/"-delimited path. */
export function buildTreeRows<T extends { name: string }>(items: T[]): TreeRow<T>[] {
  const root: FolderNode<T> = { path: "", folders: new Map(), files: [] };
  for (const item of items) insert(root, item);
  const rows: TreeRow<T>[] = [];
  flatten(root, 0, rows);
  return rows;
}

/**
 * Annotates every row from `buildTreeRows` with whether it should currently
 * render as collapsed-away (`.hidden`) - always the SAME rows, in the SAME
 * order, never a shorter array. See `TreeRow.hidden`'s own comment for why
 * this doesn't filter: a genuinely shorter array defeats any transition on
 * the rows that leave it, since Alpine's `x-for` can't animate that at all.
 *
 * With no query: a folder's descendants are hidden whenever `collapsed[folder.path]`
 * is true - the folder row itself is never hidden by this, so it stays
 * clickable to re-expand. `collapsed` mirrors settings-panel.ts's
 * `settingsCollapsed` (truthy = collapsed, absent/false = expanded -
 * "expanded" is the default so a brand new folder never starts hidden).
 *
 * With a query: expand-state is ignored entirely. Every folder with at
 * least one matching descendant file is shown (auto-expanded), and only
 * matching files are shown - the same policy the settings panel's own
 * search uses, so a match is never hidden inside a folder the user
 * happened to have collapsed.
 */
export function visibleTreeRows<T>(
  rows: TreeRow<T>[],
  collapsed: Record<string, boolean>,
  query: string,
  matches: (item: T) => boolean,
  previous?: TreeRow<T>[],
): TreeRow<T>[] {
  // `previous` is this function's own last output (the caller re-passes
  // it - see getColumnVisibleRows in trial-viewer.ts), not `rows`. That
  // distinction matters: `rows` typically comes from a cache
  // (getColumnTreeRows) that's built once and never touched again, so
  // every row in it permanently carries hidden: false from buildTreeRows -
  // comparing a freshly computed `hidden` against THAT would only ever
  // match for currently-visible rows, silently never reusing a reference
  // for anything that's actually hidden (most rows, in a big tree with
  // most folders collapsed). Comparing against the last real OUTPUT
  // instead - and returning that exact object when its hidden value still
  // matches - lets Alpine's x-for skip re-evaluating a row's whole DOM
  // subtree of bindings for it: x-for reassigns each retained key's scope
  // via `scope.row = newRow` on a reactive proxy (module.esm.js's
  // refreshScope), which - like any Vue-style reactive set - skips
  // triggering dependent effects when the new value is Object.is-equal to
  // the old one. Toggling one folder in a tree of hundreds of rows only
  // actually changes `hidden` for that folder's own descendants; every
  // other row keeping its exact prior reference is what keeps a click from
  // re-evaluating the whole tree's bindings instead of just the ones that
  // actually changed.
  const prevByKey = new Map<string, TreeRow<T>>();
  if (previous) for (const r of previous) prevByKey.set(r.key, r);
  const withHidden = (row: TreeRow<T>, hidden: boolean): TreeRow<T> => {
    const prev = prevByKey.get(row.key);
    return prev && prev.hidden === hidden ? prev : { ...row, hidden };
  };

  const q = query.trim();
  if (!q) {
    const hiddenPrefixes: string[] = [];
    return rows.map((row) => {
      const hidden = hiddenPrefixes.some((p) => row.path.startsWith(`${p}/`));
      if (!hidden && row.type === "folder" && collapsed[row.path]) hiddenPrefixes.push(row.path);
      return withHidden(row, hidden);
    });
  }

  const keepFolder = new Set<string>();
  const keepFile = new Set<string>();
  for (const row of rows) {
    if (row.type !== "file" || !row.item || !matches(row.item)) continue;
    keepFile.add(row.path);
    const segments = row.path.split("/");
    for (let i = 1; i < segments.length; i++) keepFolder.add(segments.slice(0, i).join("/"));
  }
  return rows.map((row) => {
    const hidden = !(
      (row.type === "folder" && keepFolder.has(row.path)) ||
      (row.type === "file" && keepFile.has(row.path))
    );
    return withHidden(row, hidden);
  });
}

/** Every distinct folder path in `rows` - the full set an expand-all/collapse-all action needs to touch. */
export function allTreeFolderPaths<T>(rows: TreeRow<T>[]): string[] {
  const out: string[] = [];
  for (const row of rows) if (row.type === "folder") out.push(row.path);
  return out;
}

/** Whether at least one row (from `visibleTreeRows`) isn't hidden - the empty-state check every caller previously did with `.length === 0` before rows stopped being filtered out entirely. */
export function anyTreeRowVisible<T>(rows: TreeRow<T>[]): boolean {
  return rows.some((r) => !r.hidden);
}

/**
 * Convenience wrapper for `buildTreeRows` over a plain array of path
 * strings (e.g. a column-name list) rather than objects with a `name`
 * field - `row.item` comes back as the plain string itself, not a `{name}`
 * wrapper, since `buildTreeRows`'s own `T extends { name: string }`
 * constraint can't be satisfied by `string` directly.
 */
export function buildTreeRowsFromNames(names: string[]): TreeRow<string>[] {
  return buildTreeRows(names.map((name) => ({ name }))).map((row) => ({
    ...row,
    item: row.item ? row.item.name : null,
  }));
}
