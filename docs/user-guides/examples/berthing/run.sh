#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "This script is not ready to run until a runtime has been written"
exit 1

mujoco-mojo run monte-carlo \
    -g simulation.generate \
    -r simulation.runtime \
    -nt 100 \
    --no-resume \
    --clean-workdir \
    -np 4 \
    --seed 42
