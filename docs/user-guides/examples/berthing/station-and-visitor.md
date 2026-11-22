# Station and Visitor

!!! abstract

    This guide builds the station and the visiting vehicle. Each carries a grapple fixture: the arm's base attaches to the station's, and the arm grabs the visitor's. The guide also adds the sky, the sun and a fixed camera that follows the visitor. The arm is the next guide.

    Each part follows the pattern from the [introduction](introduction.md): the part is a `UserData` class, and a `new` method builds it into the model and returns it. Where a part has dimensions, they are in an input class. The values carry their units through `US`, as in [the rocket example](../vlr/introduction.md#inputs).

---

## Shared Helpers

[Proximity](../../features/proximity.md) measures distances between mesh volumes, so the station, the hull and the fixtures are meshes instead of primitive `Geom`s. MuJoCo can generate a mesh itself, so no mesh file is needed. `CylinderInput` holds the radius, length and mass of a cylindrical part, and its `mesh` method uses Mojo's `MeshCylinder` to make the mesh. A generated cylinder is built along Z, and `lying_along` gives the pose that turns one to lie along X or Y.

??? example "Helper Code"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/shapes.py:shapes"
    ```

---

## Grapple Fixture

A grapple fixture is a post that sticks out of a structure, with a site on its end for the arm to grab. The station has one, which the arm's base attaches to, and the visitor has one, which the arm takes hold of. The same class makes both.

??? example "Fixture Inputs"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/fixture.py:inputs"
    ```

``` python
--8<-- "docs/user-guides/examples/berthing/fixture.py:fixture"
```

---

## Station

A station is one fixed body: a cylinder mesh that lies along Y, a grapple fixture on top for the arm's base, and the berthing point. The berthing point is a site where the arm will bring the visitor's grapple site.

??? example "Station Inputs"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/station.py:inputs"
    ```

``` python
--8<-- "docs/user-guides/examples/berthing/station.py:station"
```

---

## Visitor

A visitor is a cylindrical hull that lies along Y, with a grapple fixture on the side that faces the station. Its body has a free joint, so it can move. Since the model has no gravity, it stays at its initial position until the arm grapples and moves it.

??? example "Visitor Inputs"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/visitor.py:inputs"
    ```

``` python
--8<-- "docs/user-guides/examples/berthing/visitor.py:visitor"
```

---

## Sky and Overview Camera

Two small parts finish the scene. `Environment` is a dark gradient sky and the sun, a directional light that illuminates everything. `Overview` is a fixed camera that pivots to keep the center of mass of the arm's free end in view, which is how the [overview video](introduction.md) follows the action. It is built after the arm, since it aims at one of the arm's bodies. [Video Recording](../../features/video-recording.md) covers filming a camera.

??? example "Sky and Overview Camera Code"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/environment.py:environment"
    ```

    ``` python
    --8<-- "docs/user-guides/examples/berthing/overview.py:overview"
    ```

---

!!! success

    That completes the scene. In the next guide we build the arm.
