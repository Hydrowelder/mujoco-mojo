#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# exec replaces this shell process with the dojo server instead of forking it as a
# child; on Windows (Git Bash/MSYS), bash otherwise keeps this script file checked out
# for as long as the long-running dojo server is alive, which blocks deleting/replacing
# the workdir on a rerun
exec mujoco-mojo dojo .
