from collections.abc import Callable
from dataclasses import dataclass, field

import mujoco
import numpy as np

from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.runtime.forcing_function import ForcingFunction


@dataclass
class RuntimeManager:
    mojo_model: MojoModel

    forcing_functions: list[ForcingFunction] = field(default_factory=list)

    custom_probes: list[Callable] = field(default_factory=list)

    def resolve(self, mj_model: mujoco.MjModel):
        """Call this once after mj_loadXML to prime the caches."""
        for load in self.forcing_functions:
            load.resolve_ids(mj_model)

    def add_load(self, load: ForcingFunction):
        self.forcing_functions.append(load)

    def apply_step(self, mj_model, mj_data):
        """Calculates and injects forces into qfrc_applied or xfrc_applied."""
        for load in self.forcing_functions:
            if not load.active:
                continue
            f_world, t_world = load.calculate(mj_model, mj_data)
            f_world, t_world = np.asarray(f_world), np.asarray(t_world)

            # apply to action site
            mujoco.mj_applyFT(
                m=mj_model,
                d=mj_data,
                force=f_world,
                torque=t_world,
                # where in space the site is
                point=mj_data.site_xpos[load._action_id],
                # body the site is on
                body=mj_model.site_bodyid[load._action_id],
                # target generalized force array
                qfrc_target=mj_data.qfrc_applied,
            )

            # apply reaction force
            if load.xtion_site is not None:
                # Newton's 3rd Law
                mujoco.mj_applyFT(
                    m=mj_model,
                    d=mj_data,
                    force=-f_world,
                    torque=-t_world,
                    point=mj_data.site_xpos[load._xtion_id],
                    body=mj_model.site_bodyid[load._xtion_id],
                    qfrc_target=mj_data.qfrc_applied,
                )
