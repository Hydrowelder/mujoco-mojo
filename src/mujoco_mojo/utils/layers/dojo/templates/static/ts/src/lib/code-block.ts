// the copy button on a code block in a SensAI reply. a block is an empty
// placeholder until initSensAICodeBlocks fills it with a read-only editor, so
// the button is made there, by this, and not by the template

// how long the button shows its check mark after a copy
export const COPIED_MS = 1500;

const SVG_ATTRS =
  'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24" aria-hidden="true"';
const COPY_ICON = `<svg ${SVG_ATTRS} stroke-width="1.75"><path d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>`;
const CHECK_ICON = `<svg ${SVG_ATTRS} stroke-width="2.25"><path d="M5 13l4 4L19 7"/></svg>`;

// adds a button to `block` that copies `code` through `copy`, which says
// whether the copy worked. the button shows a check mark for a moment after a
// copy that did, and is left as it was after one that did not (the copy
// reports its own failure). a second click while the check mark is up keeps it
// for a full moment after that click
export function addCopyButton(
  block: HTMLElement,
  code: string,
  copy: (text: string) => Promise<boolean>,
): HTMLButtonElement {
  const button = document.createElement("button");
  // never "submit": a reply is not in a form, but a button defaults to it
  button.type = "button";
  button.className = "sensai-cm-copy";
  button.setAttribute("aria-label", "Copy code");

  const show = (copied: boolean): void => {
    button.innerHTML = copied ? CHECK_ICON : COPY_ICON;
    button.title = copied ? "Copied" : "Copy code";
    if (copied) button.dataset["copied"] = "true";
    else delete button.dataset["copied"];
  };
  show(false);

  let timer: ReturnType<typeof setTimeout> | undefined;
  button.addEventListener("click", () => {
    void copy(code).then((ok) => {
      if (!ok) return;
      show(true);
      clearTimeout(timer);
      timer = setTimeout(() => show(false), COPIED_MS);
    });
  });

  block.appendChild(button);
  return button;
}
