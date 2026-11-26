"""
SensAI's agents, one module each.

`chat` is the Dojo's chat agent, which hands each request to a specialist: `docs` (how to use Mojo, from the docs), `job_status` (the job's progress, trials, logs and input draws), `column_manifest` (the open trial's signals) and `plot_config` (the trial viewer's plot). Each specialist is a feature the user can turn off under `sensai.features`. Only `docs` reads no Dojo state, so it is the one Reloaded uses, and the others import Dojo modules.
"""
