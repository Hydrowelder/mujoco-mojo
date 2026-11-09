// the SensAI input's placeholder: it types out an example of what can be asked,
// holds it, backspaces it, and moves on to another one drawn at random. the
// state and its timing are pure so a test can step through them without timers

export const DEFAULT_PLACEHOLDER = "Ask about your sim...";

// what SensAI can be asked, one line each and short enough for the one-line box.
// the groups are the job, the plot, the signals, and how to use Mojo
export const PLACEHOLDER_EXAMPLES: readonly string[] = [
  // the job
  "Which trials are running right now?",
  "Which trial took the longest?",
  "How fast are trials finishing?",
  "Why did my trials error?",
  "Which requirement fails most often?",
  "Compare trials 3 and 7",
  "What failed in the last few trials?",
  "Which trials had errors?",
  "How was this job started?",
  "How many trials have finished?",
  "What is the average trial time?",
  "How long until the job finishes?",
  "Is the job slowing down?",
  "Has the job stalled?",
  "Which trials missed a requirement?",
  "Why did trial 12 fail?",
  "Show the log of the last failed trial",
  "Compare the slowest and fastest trials",
  "What seed and settings did this use?",
  "Where do trials spend their time?",
  // the plot
  "Make the first line cyan",
  "Add a title to the plot",
  "Plot the x position of the box",
  "Plot the velocity of the first body",
  "Remove the second signal",
  "Make the second line dashed",
  "Show angular velocity in deg/s",
  "Apply a low-pass filter to the signal",
  "Take the derivative of the signal",
  "Set the plot title to Landing speed",
  "Use a log scale on the y axis",
  "Add a vertical line at 2 seconds",
  "Label the y axis Speed",
  "Show the failed trials in versus mode",
  "Compare this trial with trials 3 and 7",
  // the signals
  "What signals are available?",
  "List the velocity signals",
  "Which signals can be rotated?",
  "What orientation signals exist?",
  // how to use Mojo
  "How do I run a Monte Carlo job?",
  "How do I submit a job to SLURM?",
  "How do I add a requirement?",
  "How do I start a new project?",
  "How do I write a runtime script?",
  "How do I set a random seed?",
  "How do I resume a stopped job?",
  "How do I watch a job on SLURM?",
  "How do I view my model in Reloaded?",
  "How do I run an optimization?",
  "How do I record a video?",
  "How do I install Mojo?",
  "What does mujoco-mojo init do?",
  "What examples are there?",
];

// how long each step takes: a character typed, a character backspaced (quicker,
// as a deletion is), how long a finished example stays, and the empty pause
// before the next one begins
export const TYPE_MS = 45;
export const ERASE_MS = 22;
export const HOLD_MS = 6000;
export const GAP_MS = 350;

export type TyperPhase = "typing" | "holding" | "erasing" | "waiting";

export interface Typer {
  // the whole example being typed or erased
  target: string;
  // how many of its characters are showing
  shown: number;
  phase: TyperPhase;
}

// the placeholder as it first appears: the default text, all of it, which stays
// for HOLD_MS before it is backspaced
export function startTyper(text: string = DEFAULT_PLACEHOLDER): Typer {
  return { target: text, shown: text.length, phase: "holding" };
}

export function visibleText(typer: Typer): string {
  return typer.target.slice(0, typer.shown);
}

// a random example other than `previous`, so the same one never comes up twice in
// a row. `random` is Math.random unless a test passes its own
export function pickNext(
  previous: string,
  options: readonly string[] = PLACEHOLDER_EXAMPLES,
  random: () => number = Math.random,
): string {
  const others = options.filter((option) => option !== previous);
  const pool = others.length > 0 ? others : options;
  return (
    pool[Math.min(pool.length - 1, Math.floor(random() * pool.length))] ??
    previous
  );
}

// one step: what is showing now, and how long to wait before the next step.
// `pick` chooses the next example once the screen is empty
export function advance(
  typer: Typer,
  pick: (previous: string) => string,
): { typer: Typer; delay: number } {
  switch (typer.phase) {
    case "typing": {
      const shown = typer.shown + 1;
      return shown >= typer.target.length
        ? {
            typer: { ...typer, shown: typer.target.length, phase: "holding" },
            delay: HOLD_MS,
          }
        : { typer: { ...typer, shown }, delay: TYPE_MS };
    }
    case "holding":
    case "erasing": {
      const shown = Math.max(0, typer.shown - 1);
      return shown === 0
        ? { typer: { ...typer, shown, phase: "waiting" }, delay: GAP_MS }
        : { typer: { ...typer, shown, phase: "erasing" }, delay: ERASE_MS };
    }
    case "waiting": {
      const target = pick(typer.target);
      return target.length <= 1
        ? {
            typer: { target, shown: target.length, phase: "holding" },
            delay: HOLD_MS,
          }
        : { typer: { target, shown: 1, phase: "typing" }, delay: TYPE_MS };
    }
  }
}
