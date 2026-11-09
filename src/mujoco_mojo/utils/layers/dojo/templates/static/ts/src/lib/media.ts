// the trial viewer's media player: which files can be scrubbed, the playback
// line and frame markers drawn over the plot, and the floating miniplayer.
// moved out of trial-viewer.ts so the decisions and the maths can be tested
// without a video element; the component still owns the elements and timers.

// a video can be scrubbed against the plot; a gif can once it has been
// converted to a video
export function isScrubbable(selected: string | null | undefined, gifStatus: string): boolean {
  const sel = selected?.toLowerCase() ?? "";
  return (
    sel.endsWith(".mp4") ||
    sel.endsWith(".webm") ||
    (sel.endsWith(".gif") && gifStatus === "ready")
  );
}

// seconds between frames at a frame rate, or null when there is no usable rate
export function frameInterval(fps: number | null | undefined): number | null {
  return fps && fps > 0 ? 1 / fps : null;
}

// the file URL with an mtime cache-buster, so a regenerated file with the same
// name forces the browser to reload it instead of reusing a stale cached copy
export function mediaUrl(
  trialId: string,
  filename: string,
  suffix: string,
  mtime: number | undefined,
): string {
  const base = `/mosaic/${trialId}/media/${filename}${suffix}`;
  return mtime !== undefined ? `${base}?t=${mtime}` : base;
}

// the saved choice if it is still one of the files, else the first
export function pickSelectedMedia(names: string[], saved: string | null): string | undefined {
  return saved && names.includes(saved) ? saved : names[0];
}

export interface OverlayInput {
  showLine: boolean;
  scrubMode: string;
  isScrubbable: boolean;
  showFrames: boolean;
  frameInterval: number | null;
  xCol: string | undefined;
  hasYAxes: boolean;
}

// frame markers need a known frame rate and a plot of signals against time
export function framesVisible(i: OverlayInput): boolean {
  return (
    i.showFrames &&
    !!i.frameInterval &&
    i.xCol === "time" &&
    i.hasYAxes
  );
}

// the overlay on the plot shows when either the playback line or the frame
// markers do; the line only while playing a scrubbable video against time.
export function overlayVisibility(i: OverlayInput): { overlay: "block" | "none"; line: "block" | "none" } {
  const lineVisible =
    i.showLine &&
    i.scrubMode === "play" &&
    i.isScrubbable &&
    i.xCol === "time" &&
    i.hasYAxes;
  return {
    overlay: lineVisible || framesVisible(i) ? "block" : "none",
    line: lineVisible ? "block" : "none",
  };
}

export interface PlaybackState {
  scrubMode: string;
  fileCount: number;
  isScrubbable: boolean;
  isTimeAxis: boolean;
  plotType: string | undefined;
}

// the playback loop only runs on a time axis: the line, zoom-looping and frame
// markers all need it. A polar plot has no x axis to read a range from.
export function shouldRunPlayback(s: PlaybackState): boolean {
  return (
    s.scrubMode === "play" &&
    s.fileCount > 0 &&
    s.isScrubbable &&
    s.isTimeAxis &&
    s.plotType !== "polar"
  );
}

// where playback jumps to when it leaves the plot's visible time range, so the
// video loops over whatever is zoomed in on: the start of the visible range
// (clamped to the video), or null when it is already inside it or the range
// is empty.
export function loopedTime(
  currentTime: number,
  xMin: number,
  xMax: number,
  duration: number,
): number | null {
  const safeMin = Math.max(0, xMin);
  const safeMax = Math.min(duration, xMax);
  if (safeMax > safeMin) {
    if (currentTime >= safeMax) return safeMin;
    if (currentTime < safeMin) return safeMin;
  }
  return null;
}

// the time to draw the playback line at: snapped to the nearest frame when the
// frame rate is known
export function snappedTime(currentTime: number, interval: number | null): number {
  return interval ? Math.round(currentTime / interval) * interval : currentTime;
}

export interface FrameMarkerInput {
  interval: number;
  // the video's length, or Infinity when it is not known yet
  duration: number;
  // the plot's height and its bottom and left margins
  height: number;
  marginB: number;
  marginL: number;
  // the visible time range
  range: [number, number];
  // an x value in axis units to a pixel offset within the plot area
  l2p: (v: number) => number;
}

// the svg path of the frame markers: a short tick at every frame time inside
// the visible range (and the video), just above the x-axis labels.
export function frameMarkersPath(f: FrameMarkerInput): string {
  const markerHeight = 5;
  const markerTop = f.height - f.marginB - 20;
  const markerBot = markerTop - markerHeight;
  const [xMin, xMax] = f.range;
  const kStart = Math.max(0, Math.floor(xMin / f.interval));
  const kEnd = Math.ceil(
    Math.min(isFinite(f.duration) ? f.duration : xMax, xMax) / f.interval,
  );
  let d = "";
  for (let k = kStart; k <= kEnd; k++) {
    const px = f.marginL + f.l2p(k * f.interval);
    d += `M${px},${markerTop}L${px},${markerBot}`;
  }
  return d;
}

// the video's length for the frame markers: its duration once it has loaded
// and is finite, else Infinity.
export function knownDuration(duration: number | undefined): number {
  return duration && isFinite(duration) ? duration : Infinity;
}

// where the miniplayer goes while it is dragged: moved by the mouse, kept at
// least 4px inside the card it floats over (and, with no card, only off the
// top left).
export function miniDragPosition(
  startLeft: number,
  startTop: number,
  dx: number,
  dy: number,
  card: { width: number; height: number; wrapperWidth: number; wrapperHeight: number } | null,
): { left: number; top: number } {
  const maxLeft = card ? Math.max(0, card.width - card.wrapperWidth - 4) : 9999;
  const maxTop = card ? Math.max(0, card.height - card.wrapperHeight - 4) : 9999;
  return {
    left: Math.max(4, Math.min(maxLeft, startLeft + dx)),
    top: Math.max(4, Math.min(maxTop, startTop + dy)),
  };
}

// the video's own shape, or 16:9 until it is known
export function aspectRatio(videoWidth: number | undefined, videoHeight: number | undefined): number {
  return videoWidth && videoHeight ? videoWidth / videoHeight : 16 / 9;
}

// the miniplayer's size while it is resized from its corner: grown by the
// mouse, never below 120x68, and with shift held kept to the video's shape,
// following whichever direction the mouse moved more.
export function miniResizeSize(
  startW: number,
  startH: number,
  dw: number,
  dh: number,
  shift: boolean,
  aspect: number,
): { width: number; height: number } {
  let newW = Math.max(120, startW + dw);
  let newH = Math.max(68, startH + dh);
  if (shift) {
    if (Math.abs(dw) >= Math.abs(dh)) {
      newH = Math.max(68, Math.round(newW / aspect));
    } else {
      newW = Math.max(120, Math.round(newH * aspect));
    }
  }
  return { width: newW, height: newH };
}

// the miniplayer copies from the video, or from the gif image until the gif
// has been converted to a video
export function miniUsesVideo(isGif: boolean, gifStatus: string): boolean {
  return !isGif || gifStatus === "ready";
}

// a frame is worth drawing once a video has enough data (a gif always is)
export function miniFrameReady(isGif: boolean, readyState: number | undefined): boolean {
  return isGif || readyState === undefined || readyState >= 2;
}
