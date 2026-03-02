from pathlib import Path

import uvicorn

from mujoco_mojo.utils.dashboard import dashboard_app
from mujoco_mojo.utils.statusing import JobStatus

workdir = (Path(__file__).parent / "./dashboard_test").resolve()
job = JobStatus.model_validate_json((workdir / "status.json").read_text())
job.refresh_from_disk(n_proc=4)

import mujoco_mojo.utils.dashboard

mujoco_mojo.utils.dashboard.CURRENT_JOB = job

if __name__ == "__main__":
    uvicorn.run(dashboard_app, host="127.0.0.1", port=8000)
