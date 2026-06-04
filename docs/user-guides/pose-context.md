# Pose Context

!!! abstract
    MJCF poses are always relative to a parent body. **Pose Context** lets you express any element's pose relative to a frame on a different branch of the kinematic tree, without walking the chain manually.

---

## The Problem

When building a kinematic tree, every body and site stores its pose relative to its immediate parent. If you want to place a site on `gripper` at the same world location as `target_site` on `base` (two separate branches) there is no direct MJCF mechanism for it. You would have to compose the full transform chain by hand.

```python
--8<-- "docs/user-guides/pose_context_example.py:build-tree"
```

---

## One-Shot Resolution

For a single pose, `Mujoco.local_pose(frame, relative_to)` resolves the pose in one call. The result is a concrete `PoseQuat` you can assign directly to any MJCF element.

```python
--8<-- "docs/user-guides/pose_context_example.py:one-shot"
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
--8<-- "docs/user-guides/pose_context_example.py:batch"
```

---

## Using `Frame` as a Reference

MJCF `Frame` elements are coordinate transforms that disappear at compile time, accumulating into their children. They are fully supported as `frame` or `relative_to` arguments.

```python
--8<-- "docs/user-guides/pose_context_example.py:frame-ref"
```

---

!!! success
    You can now place elements precisely anywhere in the kinematic tree without manually composing transform chains. Use `local_pose` for quick one-off resolutions and `PoseRef` when you want to define the reference early and resolve it later in your generate function.
