#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

mujoco-mojo reloaded \
    -g simulation.generate \
    -r simulation.runtime \
    --record
