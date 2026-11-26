# SensAI

!!! abstract

    **SensAI** is an optional assistant that answers in plain language, using a language model that you choose and provide a key for. It works in two places:

    - **The Dojo:** the [SensAI chat](dojo/sensai.md) on every page answers questions about your job and its trials, changes your plot, compares trials in [versus mode](dojo/mosaic.md#versus-mode), and explains how to use Mojo.
    - **Reloaded:** the [`sensai` command](reloaded.md#asking-sensai) answers how to use Mojo, from the docs.

    SensAI is still **experimental**. It is an AI assistant and can make mistakes, so please verify its answers and any changes it makes before relying on them. It is not a code assistant: it reads the Mojo docs and, in the Dojo, the job and plot you have open, but never your project's code. Nothing is sent anywhere until you turn it on.

---

## Setting it up

SensAI needs the `sensai` extra, and a model.

**1. Install the extra.**

``` bash linenums="0"
uv add "mujoco-mojo[sensai]"      # or: pip install "mujoco-mojo[sensai]"
```

**2. Turn it on and name a model.** The easiest way is the Dojo's [settings panel](dojo/dojo.md#settings) (the gear in its toolbar): open **SensAI**, switch **Enabled** on and add an entry under **Models**. You can also set it in `~/.mujoco-mojo/settings.toml`:

``` toml
[sensai]
enabled = true
models = [
    { provider = "Google", model_name = "gemini-3.5-flash-lite" },
]
```

!!! info "Settings under `[dojo.sensai]`"

    SensAI's settings used to be under `[dojo.sensai]`. A settings file or environment variable that still uses that name is read as before, and Mojo moves the table to `[sensai]` the next time it saves the file.

**3. Give the provider your key** in the environment variable that provider reads. The best place for it is a `.env` file in your project, which Mojo reads for you every time it starts:

``` bash linenums="0"
# .env
GOOGLE_API_KEY="..."
```

Then start the Dojo or [Reloaded](reloaded.md) as usual. Both read the same settings and key:

``` bash linenums="0"
mujoco-mojo dojo ./mojo-models
```

Mojo looks for the `.env` from where it is installed and upward, not from the folder you run the command in, so it finds the one in the project that holds your virtual environment. If Mojo is installed somewhere else, such as a tool install, put the file in a folder above that install, or set the variable in your shell instead. Add `.env` to your `.gitignore`, so the key is never committed.

To use a key for one session only, set it in your shell before you start the Dojo or Reloaded. A variable set in the shell takes priority over the `.env`:

``` bash linenums="0"
export GOOGLE_API_KEY="..."
mujoco-mojo dojo ./mojo-models
```

SensAI reads the key from the environment and never stores it in the settings file.

### Choosing models

`models` is a list, and the order matters: SensAI tries the first entry, and **falls back** to the next when a model cannot answer, for example when you hit a free tier's rate limit. Each entry has:

| Field        | Meaning                                                                                                                                       |
| :----------- | :-------------------------------------------------------------------------------------------------------------------------------------------- |
| `provider`   | Who serves the model. One of the providers below.                                                                                             |
| `model_name` | That provider's own name for the model, such as `gemini-3.5-flash-lite`.                                                                      |
| `base_url`   | Optional. Send this entry's requests to this address instead of the provider's usual one, for example a gateway or a proxy. Ollama needs one. |

The Provider menu in the settings panel shows the variable for each choice.

???+ example "Example: A local model with Ollama, and a cloud model as a backup"

    Ollama has no default address, so give each Ollama entry its own `base_url`:

    ``` toml
    [sensai]
    enabled = true
    models = [
        { provider = "Ollama", model_name = "llama3.1", base_url = "http://localhost:11434/v1" },
        { provider = "Google", model_name = "gemini-3.5-flash-lite" },
    ]
    ```

???+ info "Anthropic with a bearer token"

    Anthropic is usually reached with `ANTHROPIC_API_KEY`. If your organization uses a gateway that expects a bearer token, set `ANTHROPIC_AUTH_TOKEN` instead, and SensAI sends it as an `Authorization: Bearer` header. When both are set, the key is used. Put the gateway's address in the entry's `base_url`, or in `ANTHROPIC_BASE_URL`.

A provider whose client does not accept a `base_url` (not every one does) refuses the setting with an error that names the provider, rather than quietly sending your requests somewhere else.

### Limits

Two settings keep a message from running away:

| Setting                    | Default | What it limits                                                                                                                                            |
| :------------------------- | :------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sensai.max_requests`      | 12      | The most model requests one message may make. A message that goes over is stopped with an error that names this setting, and your plot is left as it was. |
| `sensai.max_versus_trials` | 50      | The most trials one message may add to [versus mode](dojo/mosaic.md#versus-mode), since each one loads its data. Ask again to add the next batch.         |

`max_requests` limits each question in Reloaded the same way.

### Choosing what it can do

SensAI hands each request to a specialist, and you can switch any of them off under `[sensai.features]` (**SensAI > Features** in the settings panel). One that is off is not offered to SensAI at all, and SensAI tells you it is turned off when you ask for it.

| Setting                      | What SensAI can do with it                                                                                                  |
| :--------------------------- | :-------------------------------------------------------------------------------------------------------------------------- |
| `sensai.features.docs`       | Answer how to use Mojo, what a setting does and what changed in a release, from the docs that ship with Mojo.               |
| `sensai.features.job_status` | Answer questions about the job: its progress, its trials and their timing, errors and logs, and the inputs each trial drew. |
| `sensai.features.signals`    | Say which signals the open trial recorded.                                                                                  |
| `sensai.features.plot`       | Read and change the trial viewer's plot, load saved plot profiles, and compare trials in versus mode.                       |

All four are on by default. Reloaded only uses `docs`, so with that one off, its `sensai` command says so and asks nothing.

``` toml
[sensai.features]
plot = false
```

---

!!! tip "Getting a good answer"

    Ask for one thing at a time, and name what you are asking about. If SensAI stops with an error about the number of requests, raise `sensai.max_requests` or split the question. For questions about a job or a plot, the [SensAI chat](dojo/sensai.md) guide has more tips.
