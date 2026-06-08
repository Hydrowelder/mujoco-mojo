#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

mujoco-mojo run monte-carlo \
    -g simulation.generate \
    -r simulation.runtime \
    -w ./results \
    -nt 100 \
    --no-resume \
    -cw \
    -np 4 \
    --seed 42
