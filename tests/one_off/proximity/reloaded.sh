#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

mujoco-mojo reloaded \
    -g simulation.generate \
    -r simulation.runtime \
    -ui viser \
    -h 0.0.0.0 \
    -p 5001 \
    --record
