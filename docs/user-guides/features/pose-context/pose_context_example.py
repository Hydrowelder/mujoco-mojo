import numpy as np

import mujoco_mojo as mojo

# --8<-- [start:build-tree]
# `base` and `gripper` are separate bodies, both direct children of worldbody.
# Neither is a parent of the other (they are on different branches of the tree).
base = mojo.Body(
    name=mojo.BodyName("base"), pose=mojo.PoseQuat(pos=np.array([1.0, 0.0, 0.0]))
)

# `target_site` is on `base`, so its pose ([0, 0, 0.5]) is local to `base`.
# Its world position is therefore [1.0, 0.0, 0.5].
target_site = mojo.SiteSphere(
    name=mojo.SiteName("target"), pose=mojo.PoseQuat(pos=np.array([0.0, 0.0, 0.5]))
)
base.sites.append(target_site)

# `gripper` is on a completely different branch. We want to place a site on
# it at the same world position as `target_site`, but MJCF only accepts poses
# relative to the direct parent body. There is no built-in way to say
# "put this site wherever target_site is" across branches.
gripper = mojo.Body(
    name=mojo.BodyName("gripper"), pose=mojo.PoseQuat(pos=np.array([-1.0, 0.0, 0.0]))
)

mojo_model = mojo.MojoModel()
mojo_model.mjcf.worldbody = mojo.WorldBody()
mojo_model.mjcf.worldbody.bodies.extend([base, gripper])
# --8<-- [end:build-tree]


# --8<-- [start:one-shot]
# local_pose takes the objects themselves (not their pose values) because it
# needs to walk each object's parent chain up to worldbody to compose the
# full world-space transform. A bare PoseQuat contains no tree context.
# relative_to must match the parent body of whatever element receives this pose.
local_pose = mojo_model.mjcf.local_pose(frame=target_site, relative_to=gripper)

mirror = mojo.SiteSphere(name=mojo.SiteName("mirror"), pose=local_pose)
gripper.sites.append(mirror)
# --8<-- [end:one-shot]


# --8<-- [start:batch]
# PoseRef stores the reference and resolves it on demand via the mjcf model
contact_site = mojo.SiteSphere(
    name=mojo.SiteName("contact"),
    pose=mojo.PoseRef(frame=target_site, relative_to=gripper).to_quat(mojo_model.mjcf),
)
origin_in_gripper = mojo.PoseRef(frame=base, relative_to=gripper).to_quat(
    mojo_model.mjcf
)
# --8<-- [end:batch]


# --8<-- [start:frame-ref]
# Frame elements are also valid references
alignment_frame = mojo.Frame(pose=mojo.PoseQuat(pos=np.array([0.0, 0.5, 0.0])))
base.frames.append(alignment_frame)

frame_in_gripper = mojo.PoseRef(frame=alignment_frame, relative_to=gripper).to_quat(
    mojo_model.mjcf
)
# --8<-- [end:frame-ref]
