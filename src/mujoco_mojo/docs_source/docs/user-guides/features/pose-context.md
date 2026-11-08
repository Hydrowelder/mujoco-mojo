# Pose Context

!!! abstract

    MJCF poses are always relative to a parent body. **Pose Context** lets you express any element's pose relative to a frame on a different branch of the kinematic tree, without walking the chain manually.

---

## The Problem

When building a kinematic tree, every body and site stores its pose relative to its immediate parent. If you want to place a site on `gripper` at the same world location as `target_site` on `base` (two separate branches) there is no direct MJCF mechanism for it. You would have to compose the full transform chain by hand.

```python
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
```

---

## One-Shot Resolution

For a single pose, `Mujoco.local_pose(frame, relative_to)` resolves the pose in one call. The result is a concrete `PoseQuat` you can assign directly to any MJCF element.

```python
# local_pose takes the objects themselves (not their pose values) because it
# needs to walk each object's parent chain up to worldbody to compose the
# full world-space transform. A bare PoseQuat contains no tree context.
# relative_to must match the parent body of whatever element receives this pose.
local_pose = mojo_model.mjcf.local_pose(frame=target_site, relative_to=gripper)

mirror = mojo.SiteSphere(name=mojo.SiteName("mirror"), pose=local_pose)
gripper.sites.append(mirror)
```

`frame` and `relative_to` accept any object that carries a `pose` attribute: `Body`, any site type, `Frame`, `Camera`, `Light`, and so on.

???+ warning "Warning: Match relative_to to the element's parent"

    `relative_to` must be the direct parent body of the element that will receive the resolved pose. If you assign the result to a site on `arm` but pass `relative_to=gripper`, the pose will be mathematically correct in the wrong coordinate frame and the element will appear in the wrong location.

???+ warning "Warning: Tree must be complete"

    Both `frame` and `relative_to` must be part of `mojo_model.mjcf.worldbody` at the time of the call. This is the same requirement MuJoCo has for compiling the model - anything not attached to the world will not appear in `MjModel`.

---

## Deferred Resolution with `PoseRef`

`PoseRef` stores the `frame` and `relative_to` pair and resolves lazily by passing `mojo_model.mjcf` to `.to_quat()`. This is useful when you want to define references early and resolve them later, or apply the same reference in multiple places.

```python
# PoseRef stores the reference and resolves it on demand via the mjcf model
contact_site = mojo.SiteSphere(
    name=mojo.SiteName("contact"),
    pose=mojo.PoseRef(frame=target_site, relative_to=gripper).to_quat(mojo_model.mjcf),
)
origin_in_gripper = mojo.PoseRef(frame=base, relative_to=gripper).to_quat(
    mojo_model.mjcf
)
```

---

## Using `Frame` as a Reference

MJCF `Frame` elements are coordinate transforms that disappear at compile time, accumulating into their children. They are fully supported as `frame` or `relative_to` arguments.

```python
# Frame elements are also valid references
alignment_frame = mojo.Frame(pose=mojo.PoseQuat(pos=np.array([0.0, 0.5, 0.0])))
base.frames.append(alignment_frame)

frame_in_gripper = mojo.PoseRef(frame=alignment_frame, relative_to=gripper).to_quat(
    mojo_model.mjcf
)
```

???+ warning "Scaled Frames"

    A `Frame` can scale its contents with `scale`. Pose context only composes rigid transforms, so resolving a pose for an element inside a frame whose `scale` is not 1 raises a `ValueError`. The scaled frame itself, and anything outside it, resolve as usual.

---

!!! success

    You can now place elements precisely anywhere in the kinematic tree without manually composing transform chains. Use `local_pose` for quick one-off resolutions and `PoseRef` when you want to define the reference early and resolve it later in your generate function.
