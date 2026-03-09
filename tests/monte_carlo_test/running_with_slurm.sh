# 1. Enter the controller
docker exec -it slurmctld bash

# ================ ONETIME SETP ================
# install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH=$PATH:/root/.local/bin

# start a venv
python3 -m venv /home/mujoco-mojo-dev/.slurm_venv
source .slurm_venv/bin/activate
pip install uv

# install packages
uv pip install -e ./mujoco-mojo
uv pip install -e ./process_manager

# 2. Move to the workspace
cd /home/mujoco-mojo-dev
source .slurm_venv/bin/activate

# 3. Run the command
mujoco-mojo run monte-carlo \
    -g mujoco-mojo.tests.monte_carlo_test.monte_carlo.generate \
    -r mujoco-mojo.tests.monte_carlo_test.monte_carlo.runtime \
    -w /home/mujoco-mojo-dev/mujoco-mojo/tests/monte_carlo_test/mc_test \
    -nt 100 \
    --no-resume \
    -cw \
    -np 1 \
    --seed 42 \
    --overrides /home/mujoco-mojo-dev/mujoco-mojo/tests/monte_carlo_test/overrides.json \
    --execution-mode slurm
