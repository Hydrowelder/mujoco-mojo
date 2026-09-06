// bridges iro.js's npm import into partials/trial_viewer/_macros.html's
// color_picker macro. Only the construction moves here -- the $watch /
// color:change reactive wiring stays inline in that macro's x-init since it
// depends on Alpine's magic properties and per-call-site Jinja-interpolated
// expressions (the bound `color_model` property, the `on_change` callback),
// which can't cross into a bundled TS module cleanly.
import iro from "@jaames/iro";

window.mojoCreateColorPicker = (el, width, boxHeight, initialColor) =>
  iro.ColorPicker(el, {
    width,
    height: width,
    color: initialColor,
    padding: 0,
    handleRadius: 9,
    borderWidth: 1,
    borderColor: "#000000",
    layout: [
      { component: iro.ui.Box, options: { margin: 10, width, boxHeight } },
      {
        component: iro.ui.Slider,
        options: { sliderType: "hue", width, height: 20, margin: 10 },
      },
    ],
  });
