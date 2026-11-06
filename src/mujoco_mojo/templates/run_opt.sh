#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

mujoco-mojo run optimization \
    -g simulation.generate \
    -r simulation.runtime \
    -ob simulation.objective \
    -nt 100 \
    --no-resume \
    --clean-workdir \
    -np 4 \
    --seed 42
