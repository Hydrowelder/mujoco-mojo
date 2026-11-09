// undo history for the plot config: a stack of JSON snapshots and the index of
// the current one

export interface History {
  stack: string[];
  index: number;
}

// the history after recording `snapshot` as the newest state, or null when it
// is the state already current (so nothing changes). recording after an undo
// discards the undone states ahead of the index, and the oldest snapshot drops
// off once the stack outgrows `max`
export function pushSnapshot(history: History, snapshot: string, max: number): History | null {
  if (history.stack[history.index] === snapshot) return null;
  const stack = history.stack.slice(0, history.index + 1);
  stack.push(snapshot);
  if (stack.length > max) stack.shift();
  return { stack, index: stack.length - 1 };
}
