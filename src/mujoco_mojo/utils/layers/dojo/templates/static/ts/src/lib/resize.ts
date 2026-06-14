// Shared drag-to-resize handle for vertically resizable panels (JSON editor,
// chart area, ...). Persists the resulting height to localStorage and
// restores it on the next load.

export interface ResizeHandleOptions {
  /** localStorage key the resulting height (e.g. "420px") is stored under. */
  storageKey: string;
  /** Minimum height in pixels while dragging. Defaults to 128. */
  minHeight?: number;
  /** Called with the new height (px) while dragging and after a reset. */
  onResize?: (heightPx: number) => void;
  /** Double-click handler returning a CSS height to reset to, or undefined to ignore. */
  getResetHeight?: () => string | undefined;
}

/** Apply a previously persisted height to `hostEl`, if one was saved. */
export function restorePersistedHeight(hostEl: HTMLElement, storageKey: string): void {
  const saved = localStorage.getItem(storageKey);
  if (saved) hostEl.style.height = saved;
}

/**
 * Insert a draggable resize handle directly after `hostEl` that adjusts
 * `hostEl`'s height. Returns the handle element.
 */
export function attachVerticalResizeHandle(
  hostEl: HTMLElement,
  options: ResizeHandleOptions,
): HTMLElement {
  const minHeight = options.minHeight ?? 128;

  const persist = (height: string) => {
    try {
      localStorage.setItem(options.storageKey, height);
    } catch {
      /* ignore */
    }
  };

  const handle = document.createElement("div");
  handle.style.cssText =
    "height:14px;cursor:ns-resize;display:flex;align-items:center;justify-content:center;flex-shrink:0;";
  const grip = document.createElement("div");
  grip.style.cssText =
    "width:36px;height:4px;border-radius:2px;background:#334155;transition:background 150ms,width 150ms;pointer-events:none;";
  handle.appendChild(grip);
  handle.addEventListener("mouseenter", () => {
    grip.style.background = "#06b6d4";
    grip.style.width = "52px";
  });
  handle.addEventListener("mouseleave", () => {
    grip.style.background = "#334155";
    grip.style.width = "36px";
  });

  handle.addEventListener("mousedown", (e) => {
    const startY = e.clientY;
    const startH = hostEl.offsetHeight;
    let prevY = startY;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "ns-resize";
    const onMove = (ev: MouseEvent) => {
      const dy = ev.clientY - prevY;
      prevY = ev.clientY;
      const newH = Math.max(minHeight, startH + (ev.clientY - startY));
      hostEl.style.height = newH + "px";
      options.onResize?.(newH);
      if (dy > 0) window.scrollBy(0, dy);
    };
    const onUp = () => {
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      persist(hostEl.style.height);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    e.preventDefault();
  });

  handle.addEventListener("dblclick", () => {
    const resetHeight = options.getResetHeight?.();
    if (!resetHeight) return;
    hostEl.style.height = resetHeight;
    options.onResize?.(hostEl.offsetHeight);
    persist(hostEl.style.height);
  });

  hostEl.insertAdjacentElement("afterend", handle);
  return handle;
}
