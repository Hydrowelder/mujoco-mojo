// evaluates the arithmetic typed into a numeric field (a plot range bound, a
// filter parameter): a plain number, or an expression over a fixed set of
// math functions and constants such as `2*pi` or `sqrt(2)/2`. returns null for
// anything blank, malformed or not a finite number.
//
// the expression is read by a small parser rather than handed to the
// javascript engine, so nothing outside the grammar below can run: numbers,
// `+ - * / %`, `^` and `**` for a power (right to left, `2^3^2` is 512),
// unary `+` and `-` (looser than the power, so `-2^2` is -4), parentheses,
// the constants in CONSTANTS and the functions in FUNCTIONS.

const CONSTANTS = new Map<string, number>([
  ["pi", Math.PI],
  ["e", Math.E],
]);

const FUNCTIONS = new Map<string, (...args: number[]) => number>([
  ["sin", Math.sin],
  ["cos", Math.cos],
  ["tan", Math.tan],
  ["asin", Math.asin],
  ["acos", Math.acos],
  ["atan", Math.atan],
  ["atan2", Math.atan2],
  ["sqrt", Math.sqrt],
  ["cbrt", Math.cbrt],
  ["log", Math.log],
  ["log2", Math.log2],
  ["log10", Math.log10],
  ["abs", Math.abs],
  ["floor", Math.floor],
  ["ceil", Math.ceil],
  ["round", Math.round],
  ["sign", Math.sign],
  ["pow", Math.pow],
  ["exp", Math.exp],
  ["max", Math.max],
  ["min", Math.min],
]);

type Token =
  | { kind: "num"; value: number }
  | { kind: "id"; name: string }
  | { kind: "op"; op: string };

const NUMBER = /^(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?/;
const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*/;
const OPERATOR = /^(?:\*\*|[-+*/%^(),])/;

function invalid(): never {
  throw new Error("invalid expression");
}

function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  let rest = text;
  while (rest.length > 0) {
    const space = /^\s+/.exec(rest);
    const num = NUMBER.exec(rest);
    const id = IDENTIFIER.exec(rest);
    const op = OPERATOR.exec(rest);
    if (space) {
      rest = rest.slice(space[0].length);
    } else if (num) {
      tokens.push({ kind: "num", value: Number(num[0]) });
      rest = rest.slice(num[0].length);
    } else if (id) {
      tokens.push({ kind: "id", name: id[0] });
      rest = rest.slice(id[0].length);
    } else if (op) {
      tokens.push({ kind: "op", op: op[0] });
      rest = rest.slice(op[0].length);
    } else {
      invalid();
    }
  }
  return tokens;
}

// the value of the whole token list, or an error for anything that is not an expression
function parse(tokens: Token[]): number {
  let pos = 0;

  // the operator at the current token if it is one of `ops`, else null
  const peek = (...ops: string[]): string | null => {
    const t = tokens[pos];
    return t?.kind === "op" && ops.includes(t.op) ? t.op : null;
  };

  const sum = (): number => {
    let value = product();
    for (let op = peek("+", "-"); op; op = peek("+", "-")) {
      pos++;
      const right = product();
      value = op === "+" ? value + right : value - right;
    }
    return value;
  };

  const product = (): number => {
    let value = unary();
    for (let op = peek("*", "/", "%"); op; op = peek("*", "/", "%")) {
      pos++;
      const right = unary();
      value = op === "*" ? value * right : op === "/" ? value / right : value % right;
    }
    return value;
  };

  const unary = (): number => {
    const op = peek("+", "-");
    if (op) {
      pos++;
      const value = unary();
      return op === "-" ? -value : value;
    }
    return power();
  };

  // the exponent is a unary, so `2^-1` works and `2^3^2` groups to the right
  const power = (): number => {
    const base = atom();
    if (peek("^", "**")) {
      pos++;
      return Math.pow(base, unary());
    }
    return base;
  };

  const atom = (): number => {
    const t = tokens[pos++];
    if (t?.kind === "num") return t.value;
    if (t?.kind === "op" && t.op === "(") {
      const value = sum();
      if (!peek(")")) invalid();
      pos++;
      return value;
    }
    if (t?.kind === "id") {
      if (peek("(")) {
        const fn = FUNCTIONS.get(t.name) ?? invalid();
        pos++;
        return fn(...args());
      }
      return CONSTANTS.get(t.name) ?? invalid();
    }
    return invalid();
  };

  // the comma-separated arguments of a call, up to and including its `)`
  const args = (): number[] => {
    const values: number[] = [];
    if (peek(")")) {
      pos++;
      return values;
    }
    for (;;) {
      values.push(sum());
      if (peek(",")) {
        pos++;
      } else if (peek(")")) {
        pos++;
        return values;
      } else {
        return invalid();
      }
    }
  };

  const value = sum();
  if (pos !== tokens.length) invalid();
  return value;
}

export function evalMathExpr(expr: string): number | null {
  const s = String(expr ?? "").trim();
  if (!s) return null;
  const n = Number(s);
  if (isFinite(n)) return n;
  try {
    const result = parse(tokenize(s));
    if (isFinite(result)) return result;
  } catch {
    // not an expression - fall through
  }
  return null;
}
