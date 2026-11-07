import { describe, expect, it } from "vitest";

import {
  aspectRatio,
  frameInterval,
  frameMarkersPath,
  framesVisible,
  isScrubbable,
  knownDuration,
  loopedTime,
  mediaUrl,
  miniDragPosition,
  miniFrameReady,
  miniResizeSize,
  miniUsesVideo,
  overlayVisibility,
  pickSelectedMedia,
  shouldRunPlayback,
  snappedTime,
  type OverlayInput,
  type PlaybackState,
} from "./media";

describe("isScrubbable", () => {
  it("is true for a video, whatever the case of its name", () => {
    for (const name of ["a.mp4", "A.MP4", "clip.webm", "Clip.WebM"]) {
      expect(isScrubbable(name, "none")).toBe(true);
      expect(isScrubbable(name, "failed")).toBe(true);
    }
  });

  it("is true for a gif once it has been converted to a video", () => {
    expect(isScrubbable("x.gif", "ready")).toBe(true);
    expect(isScrubbable("X.GIF", "ready")).toBe(true);
  });

  it("is false for a gif that has not been converted", () => {
    for (const status of ["none", "loading", "failed"]) expect(isScrubbable("x.gif", status)).toBe(false);
  });

  it("is false for anything else", () => {
    for (const name of ["clip.mov", "y.mp4.txt", "noext", "", null, undefined]) {
      expect(isScrubbable(name, "ready")).toBe(false);
    }
  });
});

describe("frameInterval", () => {
  it("is a frame's length in seconds", () => {
    expect(frameInterval(25)).toBe(0.04);
    expect(frameInterval(1)).toBe(1);
    expect(frameInterval(29.97)).toBeCloseTo(0.033367, 5);
  });

  it("is null without a usable frame rate", () => {
    for (const fps of [0, -5, null, undefined]) expect(frameInterval(fps)).toBeNull();
  });
});

describe("mediaUrl", () => {
  it("is the file's route, with its modification time as a cache-buster", () => {
    expect(mediaUrl("run_7", "a.mp4", "", 100)).toBe("/mosaic/run_7/media/a.mp4?t=100");
  });

  it("adds a suffix to the file name before the cache-buster", () => {
    expect(mediaUrl("run_7", "a.gif", "/video", 5)).toBe("/mosaic/run_7/media/a.gif/video?t=5");
  });

  it("keeps a modification time of zero", () => {
    expect(mediaUrl("run_7", "a.mp4", "", 0)).toBe("/mosaic/run_7/media/a.mp4?t=0");
  });

  it("has no cache-buster when the modification time is unknown", () => {
    expect(mediaUrl("run_7", "a.mp4", "", undefined)).toBe("/mosaic/run_7/media/a.mp4");
  });
});

describe("pickSelectedMedia", () => {
  it("is the saved choice while it is still one of the files", () => {
    expect(pickSelectedMedia(["a.mp4", "b.gif"], "b.gif")).toBe("b.gif");
  });

  it("is the first file when nothing was saved or the saved one is gone", () => {
    expect(pickSelectedMedia(["a.mp4", "b.gif"], null)).toBe("a.mp4");
    expect(pickSelectedMedia(["a.mp4", "b.gif"], "")).toBe("a.mp4");
    expect(pickSelectedMedia(["a.mp4", "b.gif"], "gone.mp4")).toBe("a.mp4");
  });

  it("is nothing without files", () => {
    expect(pickSelectedMedia([], "a.mp4")).toBeUndefined();
  });
});

describe("overlay visibility", () => {
  const input = (over: Partial<OverlayInput> = {}): OverlayInput => ({
    showLine: true,
    scrubMode: "play",
    isScrubbable: true,
    showFrames: true,
    frameInterval: 0.04,
    xCol: "time",
    hasYAxes: true,
    ...over,
  });

  describe("framesVisible", () => {
    it("is true with frames on, a frame rate, a time axis and signals", () => {
      expect(framesVisible(input())).toBe(true);
    });

    it.each([
      ["frames off", { showFrames: false }],
      ["no frame rate", { frameInterval: null }],
      ["a zero frame interval", { frameInterval: 0 }],
      ["another x axis", { xCol: "angle" }],
      ["no x axis", { xCol: undefined }],
      ["no signals", { hasYAxes: false }],
    ] as const)("is false with %s", (_label, over) => {
      expect(framesVisible(input(over))).toBe(false);
    });
  });

  describe("overlayVisibility", () => {
    it("shows the line and the overlay while playing a scrubbable video against time", () => {
      expect(overlayVisibility(input({ showFrames: false }))).toEqual({ overlay: "block", line: "block" });
    });

    it("hides the line but keeps the overlay for frame markers alone", () => {
      expect(overlayVisibility(input({ showLine: false }))).toEqual({ overlay: "block", line: "none" });
      expect(overlayVisibility(input({ scrubMode: "scrub" }))).toEqual({ overlay: "block", line: "none" });
      expect(overlayVisibility(input({ isScrubbable: false }))).toEqual({ overlay: "block", line: "none" });
    });

    it("shows the line without frame markers when there is no frame rate", () => {
      expect(overlayVisibility(input({ frameInterval: null }))).toEqual({ overlay: "block", line: "block" });
    });

    it("hides both with neither to show", () => {
      expect(overlayVisibility(input({ showLine: false, showFrames: false }))).toEqual({ overlay: "none", line: "none" });
    });

    it("hides both off a time axis, or with no signals", () => {
      expect(overlayVisibility(input({ xCol: "angle" }))).toEqual({ overlay: "none", line: "none" });
      expect(overlayVisibility(input({ hasYAxes: false }))).toEqual({ overlay: "none", line: "none" });
      expect(overlayVisibility(input({ xCol: undefined }))).toEqual({ overlay: "none", line: "none" });
    });
  });
});

describe("shouldRunPlayback", () => {
  const state = (over: Partial<PlaybackState> = {}): PlaybackState => ({
    scrubMode: "play",
    fileCount: 1,
    isScrubbable: true,
    isTimeAxis: true,
    plotType: "cartesian",
    ...over,
  });

  it("runs while playing a scrubbable file against time on a cartesian plot", () => {
    expect(shouldRunPlayback(state())).toBe(true);
    expect(shouldRunPlayback(state({ plotType: undefined, fileCount: 5 }))).toBe(true);
  });

  it.each([
    ["scrubbing", { scrubMode: "scrub" }],
    ["no files", { fileCount: 0 }],
    ["a file that cannot be scrubbed", { isScrubbable: false }],
    ["another x axis", { isTimeAxis: false }],
    ["a polar plot", { plotType: "polar" }],
  ] as const)("does not run with %s", (_label, over) => {
    expect(shouldRunPlayback(state(over))).toBe(false);
  });
});

describe("loopedTime", () => {
  it("leaves playback alone while it is inside the visible range", () => {
    expect(loopedTime(5, 2, 8, 10)).toBeNull();
    expect(loopedTime(2, 2, 8, 10)).toBeNull();
    expect(loopedTime(7.99, 2, 8, 10)).toBeNull();
  });

  it("jumps back to the start of the range at its end", () => {
    expect(loopedTime(8, 2, 8, 10)).toBe(2);
    expect(loopedTime(9.5, 2, 8, 10)).toBe(2);
  });

  it("jumps to the start of the range from before it", () => {
    expect(loopedTime(1.9, 2, 8, 10)).toBe(2);
    expect(loopedTime(0, 2, 8, 10)).toBe(2);
  });

  it("never loops to before the start of the video", () => {
    expect(loopedTime(9, -3, 4, 10)).toBe(0);
    expect(loopedTime(-1, -3, 4, 10)).toBe(0);
  });

  it("ends the range at the end of the video", () => {
    expect(loopedTime(10, 2, 50, 10)).toBe(2);
    expect(loopedTime(9.9, 2, 50, 10)).toBeNull();
  });

  it("leaves playback alone when the range is empty or past the video", () => {
    expect(loopedTime(5, 5, 5, 10)).toBeNull();
    expect(loopedTime(5, 6, 5, 10)).toBeNull();
    expect(loopedTime(5, 12, 20, 10)).toBeNull();
  });
});

describe("snappedTime", () => {
  it("is the nearest frame time when the frame rate is known", () => {
    expect(snappedTime(1.234, 0.04)).toBeCloseTo(1.24);
    expect(snappedTime(1.219, 0.04)).toBeCloseTo(1.2);
    expect(snappedTime(0.019, 0.04)).toBe(0);
    expect(snappedTime(0.021, 0.04)).toBeCloseTo(0.04);
  });

  it("is the time itself with no frame rate", () => {
    expect(snappedTime(1.234, null)).toBe(1.234);
  });

  it("is the time itself for an interval of zero", () => {
    expect(snappedTime(1.234, 0)).toBe(1.234);
  });
});

describe("frameMarkersPath", () => {
  const base = { interval: 1, duration: Infinity, height: 300, marginB: 50, marginL: 80, range: [0, 3] as [number, number], l2p: (v: number) => v * 10 };

  it("draws a tick at every frame time in the visible range, just above the axis labels", () => {
    // top = 300 - 50 - 20 = 230, bottom = 225
    expect(frameMarkersPath(base)).toBe("M80,230L80,225M90,230L90,225M100,230L100,225M110,230L110,225");
  });

  it("starts at the first frame at or before the left edge of the range", () => {
    expect(frameMarkersPath({ ...base, range: [1.5, 3] })).toBe("M90,230L90,225M100,230L100,225M110,230L110,225");
  });

  it("starts no earlier than time zero", () => {
    expect(frameMarkersPath({ ...base, range: [-5, 1] })).toBe("M80,230L80,225M90,230L90,225");
  });

  it("stops at the end of the video when it is shorter than the range", () => {
    expect(frameMarkersPath({ ...base, duration: 1.5 })).toBe("M80,230L80,225M90,230L90,225M100,230L100,225");
  });

  it("goes by the range when the video's length is not known", () => {
    expect(frameMarkersPath({ ...base, duration: NaN })).toBe(frameMarkersPath(base));
    expect(frameMarkersPath({ ...base, duration: Infinity })).toBe(frameMarkersPath(base));
  });

  it("stops at the end of the range when the video is longer", () => {
    expect(frameMarkersPath({ ...base, duration: 100 })).toBe(frameMarkersPath(base));
  });

  it("draws one tick per frame at the interval it is given", () => {
    expect(frameMarkersPath({ ...base, interval: 0.5, range: [0, 1] })).toBe("M80,230L80,225M85,230L85,225M90,230L90,225");
  });

  it("offsets each tick by the left margin and places it with the axis scale", () => {
    expect(frameMarkersPath({ ...base, marginL: 0, range: [0, 1], l2p: (v) => v * 100 })).toBe("M0,230L0,225M100,230L100,225");
  });

  it("moves with the plot's height and bottom margin", () => {
    expect(frameMarkersPath({ ...base, height: 400, marginB: 80, range: [0, 0] })).toBe("M80,300L80,295");
  });
});

describe("knownDuration", () => {
  it("is the video's length once it is known", () => {
    expect(knownDuration(8.5)).toBe(8.5);
  });

  it("is infinite while the length is not known", () => {
    for (const d of [undefined, 0, NaN, Infinity]) expect(knownDuration(d)).toBe(Infinity);
  });
});

describe("miniDragPosition", () => {
  const card = { width: 500, height: 300, wrapperWidth: 160, wrapperHeight: 90 };

  it("follows the mouse", () => {
    expect(miniDragPosition(20, 30, 10, -5, card)).toEqual({ left: 30, top: 25 });
  });

  it("stays 4px inside the top left of the card", () => {
    expect(miniDragPosition(20, 30, -100, -100, card)).toEqual({ left: 4, top: 4 });
  });

  it("stays 4px inside the bottom right of the card", () => {
    // 500 - 160 - 4 = 336, 300 - 90 - 4 = 206
    expect(miniDragPosition(20, 30, 900, 900, card)).toEqual({ left: 336, top: 206 });
  });

  it("stays at the top left when the card is smaller than the player", () => {
    expect(miniDragPosition(20, 30, 50, 50, { width: 100, height: 60, wrapperWidth: 160, wrapperHeight: 90 })).toEqual({ left: 4, top: 4 });
  });

  it("is only held off the top left without a card", () => {
    expect(miniDragPosition(20, 30, 900, 900, null)).toEqual({ left: 920, top: 930 });
    expect(miniDragPosition(20, 30, -100, -100, null)).toEqual({ left: 4, top: 4 });
    expect(miniDragPosition(20, 30, 99999, 99999, null)).toEqual({ left: 9999, top: 9999 });
  });
});

describe("aspectRatio", () => {
  it("is the video's own shape", () => {
    expect(aspectRatio(1920, 1080)).toBeCloseTo(16 / 9);
    expect(aspectRatio(640, 640)).toBe(1);
    expect(aspectRatio(480, 640)).toBe(0.75);
  });

  it("is 16:9 until the video's size is known", () => {
    for (const [w, h] of [[0, 480], [480, 0], [undefined, undefined], [480, undefined], [undefined, 480]] as const) {
      expect(aspectRatio(w, h)).toBeCloseTo(16 / 9);
    }
  });
});

describe("miniResizeSize", () => {
  it("grows and shrinks with the mouse", () => {
    expect(miniResizeSize(240, 135, 10, -20, false, 16 / 9)).toEqual({ width: 250, height: 115 });
  });

  it("is never smaller than 120x68", () => {
    expect(miniResizeSize(240, 135, -500, -500, false, 16 / 9)).toEqual({ width: 120, height: 68 });
  });

  it("keeps the video's shape with shift, following a mostly sideways move", () => {
    expect(miniResizeSize(240, 135, 80, 10, true, 2)).toEqual({ width: 320, height: 160 });
  });

  it("keeps the video's shape with shift, following a mostly vertical move", () => {
    expect(miniResizeSize(240, 135, 10, 80, true, 2)).toEqual({ width: 430, height: 215 });
  });

  it("follows the width on a tie", () => {
    expect(miniResizeSize(240, 135, 40, 40, true, 2)).toEqual({ width: 280, height: 140 });
  });

  it("still never goes below the minimum with shift", () => {
    // a wide shape would make the height 30 from a width of 120
    expect(miniResizeSize(240, 135, -200, 0, true, 4)).toEqual({ width: 120, height: 68 });
    // a tall shape would make the width 17 from a height of 68
    expect(miniResizeSize(240, 135, 0, -100, true, 0.25)).toEqual({ width: 120, height: 68 });
  });
});

describe("miniUsesVideo", () => {
  it("copies from the video for a video, or a gif that has been converted", () => {
    expect(miniUsesVideo(false, "none")).toBe(true);
    expect(miniUsesVideo(true, "ready")).toBe(true);
  });

  it("copies from the gif image until it has been converted", () => {
    for (const status of ["none", "loading", "failed"]) expect(miniUsesVideo(true, status)).toBe(false);
  });
});

describe("miniFrameReady", () => {
  it("is always ready for a gif", () => {
    expect(miniFrameReady(true, 0)).toBe(true);
    expect(miniFrameReady(true, undefined)).toBe(true);
  });

  it("is ready once a video has data for the current frame", () => {
    expect(miniFrameReady(false, 2)).toBe(true);
    expect(miniFrameReady(false, 4)).toBe(true);
  });

  it("is not ready while a video has little or no data", () => {
    expect(miniFrameReady(false, 0)).toBe(false);
    expect(miniFrameReady(false, 1)).toBe(false);
  });

  it("is ready when there is no ready state to ask", () => {
    expect(miniFrameReady(false, undefined)).toBe(true);
  });
});
