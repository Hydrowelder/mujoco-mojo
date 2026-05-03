from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mujoco-mojo")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

__author__ = "David Gable"
__email__ = "dave.a.gable@gmail.com"
__license__ = "Apache-2.0"
__summary__ = "A complete MJCF lifecycle and trial orchestration suite for MuJoCo, powered by Pydantic v2."
