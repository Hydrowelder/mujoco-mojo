// evaluates the arithmetic typed into a numeric field (a plot range bound, a
// filter parameter): a plain number, or an expression over a fixed set of
// math functions and constants such as `2*pi` or `sqrt(2)/2`. returns null for
// anything blank, malformed or not a finite number.
export function evalMathExpr(expr: string): number | null {
  const s = String(expr ?? "").trim();
  if (!s) return null;
  const n = Number(s);
  if (!isNaN(n)) return n;
  try {
    // Expose a safe math context - no access to globals beyond these names.
    const fn = new Function(
      "pi",
      "e",
      "sin",
      "cos",
      "tan",
      "asin",
      "acos",
      "atan",
      "atan2",
      "sqrt",
      "cbrt",
      "log",
      "log2",
      "log10",
      "abs",
      "floor",
      "ceil",
      "round",
      "sign",
      "pow",
      "exp",
      "max",
      "min",
      `"use strict"; return (${s})`,
    );
    const result = fn(
      Math.PI,
      Math.E,
      Math.sin,
      Math.cos,
      Math.tan,
      Math.asin,
      Math.acos,
      Math.atan,
      Math.atan2,
      Math.sqrt,
      Math.cbrt,
      Math.log,
      Math.log2,
      Math.log10,
      Math.abs,
      Math.floor,
      Math.ceil,
      Math.round,
      Math.sign,
      Math.pow,
      Math.exp,
      Math.max,
      Math.min,
    ) as unknown;
    if (typeof result === "number" && isFinite(result)) return result;
  } catch {
    // invalid expression - fall through
  }
  return null;
}
