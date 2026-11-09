// helpers that map between a position in the JSON editor's document and a path
// through the config it holds. both read CodeMirror's own Lezer parse tree
// rather than any text or regex approach, which would be fragile against
// nested strings, escaped quotes, and so on.

import { syntaxTree, type EditorState, type SyntaxNode } from "./codemirror";
import type { SchemaPathSegment } from "./schema-validate";

// JSON editor hover tooltips (initCodeMirror's hoverTooltip extension) - the
// path of JSON object keys enclosing document position `pos`, read from
// CodeMirror's own Lezer parse tree rather than any text-based/regex
// approach, which would be fragile against nested strings, escaped quotes,
// etc. lib/json-schema.ts's describeSchemaPath then walks
// plotConfigSchema alongside this same path to find that field's
// description.
//
// @codemirror/lang-json's grammar (@lezer/json) only names three node
// types relevant here: "Property" (a key:value pair), "PropertyName" (a
// Property's own key, still-quoted string), and "Array" - object keys
// versus array items are structurally different in JSON (a key is text,
// an index is just position), so PropertyName is read for the former and
// a plain "" placeholder pushed for the latter; describeSchemaPath already
// treats any segment as "descend into .items" once the schema node it's
// standing on is itself an array, so the placeholder's actual value is
// never read, it's a pure step-marker. Walking bottom-up from `pos` (via
// resolveInner, which finds the innermost node covering that position)
// through every such ancestor and prepending each is what turns, e.g.,
// hovering the "color" in `{"yAxes": {"ax1": {"color": "#fff"}}}` into
// the path ["yAxes", "ax1", "color"] - "ax1" is an arbitrary dict key
// (PlotConfig.yAxes is dict[str, YAxisConfig]), captured the same way as
// any other PropertyName even though describeSchemaPath will treat it as
// a dict-value step rather than a fixed field lookup.
export function jsonPathAt(state: EditorState, pos: number): string[] {
  const path: string[] = [];
  let cur: SyntaxNode | null = syntaxTree(state).resolveInner(pos, -1);
  while (cur) {
    if (cur.name === "Property") {
      const nameNode = cur.getChild("PropertyName");
      if (nameNode) {
        const raw = state.doc.sliceString(nameNode.from, nameNode.to);
        try {
          path.unshift(JSON.parse(raw) as string);
        } catch {
          path.unshift(raw.slice(1, -1));
        }
      }
    } else if (cur.name === "Array") {
      path.unshift("");
    }
    cur = cur.parent;
  }
  return path;
}

// the concrete node types @lezer/json ever uses for a JSON *value* position
// (as opposed to punctuation like "{", ",", ":" - which are themselves
// nodes in the tree, just not ones a value path ever points at).
const JSON_VALUE_NODE_NAMES = new Set(["Object", "Array", "String", "Number", "True", "False", "Null"]);

function decodePropertyName(state: EditorState, nameNode: SyntaxNode): string {
  const raw = state.doc.sliceString(nameNode.from, nameNode.to);
  try {
    return JSON.parse(raw) as string;
  } catch {
    return raw.slice(1, -1);
  }
}

// Reverse of jsonPathAt: walks a *structured* path (real object keys and
// array indices, as produced by collectSchemaDiagnostics - not
// jsonPathAt's own "" placeholder for an array step, which only needs to
// know "inside some array" for a schema lookup, not which element) down
// from the document root to the exact node it names, so a schema
// validation error can underline the specific offending value instead of
// just being listed as text. Returns null if the path doesn't resolve
// (e.g. a stale diagnostic from before the day's last edit, or a key that
// was itself renamed/removed).
export function jsonRangeForPath(
  state: EditorState,
  path: SchemaPathSegment[],
): { from: number; to: number } | null {
  let node: SyntaxNode | null = syntaxTree(state).topNode.firstChild;
  for (const seg of path) {
    if (!node) return null;
    if (typeof seg === "number") {
      if (node.name !== "Array") return null;
      let child: SyntaxNode | null = node.firstChild;
      let index = -1;
      let found: SyntaxNode | null = null;
      while (child) {
        if (JSON_VALUE_NODE_NAMES.has(child.name)) {
          index += 1;
          if (index === seg) {
            found = child;
            break;
          }
        }
        child = child.nextSibling;
      }
      node = found;
    } else {
      if (node.name !== "Object") return null;
      const match = node
        .getChildren("Property")
        .find((prop) => {
          const nameNode = prop.getChild("PropertyName");
          return nameNode ? decodePropertyName(state, nameNode) === seg : false;
        });
      node = match?.lastChild ?? null;
    }
  }
  return node ? { from: node.from, to: node.to } : null;
}
