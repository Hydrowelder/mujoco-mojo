"""Unit tests for ProximityMixin class."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import mujoco
import numpy as np
import pytest

import mujoco_mojo as mojo

# ============================================================================
# Fixtures
# ============================================================================


@dataclass
class ModelWithGeoms:
    mujoco_model: mojo.Mujoco
    bunny_in_cup_geom: mojo.GeomMesh
    bunny_below_cup_geom: mojo.GeomMesh
    ball_above_cup_geom: mojo.GeomMesh
    cup_geom: mojo.GeomMesh

    def compile(self) -> tuple[mujoco.MjModel, mujoco.MjData]:
        # copy assets to shared dir
        workdir = Path(__file__).parent / "proximity_test_model"
        workdir.mkdir(exist_ok=True, parents=True)
        (workdir / ".gitignore").write_text("*")
        asset_dir = workdir / "assets"
        rel_to_xml = Path(os.path.relpath(asset_dir, workdir))
        self.mujoco_model.bundle_assets(target_dir=asset_dir, rel_to_xml=rel_to_xml)

        # prep sim
        mj_model, mj_data = self.mujoco_model.prep_for_sim(
            save_path=workdir / "mojo_model.xml"
        )
        return mj_model, mj_data


@dataclass
class CompiledModel(ModelWithGeoms):
    mj_model: mujoco.MjModel
    mj_data: mujoco.MjData

    @classmethod
    def from_model_with_geoms(cls, model_with_geoms: ModelWithGeoms) -> CompiledModel:
        mj_model, mj_data = model_with_geoms.compile()
        return cls(
            mj_model=mj_model,
            mj_data=mj_data,
            **vars(model_with_geoms),
        )


MESHES_DIR = mojo.DepPath(__file__).parent.parent / "meshes"


def _bunny_mesh_file() -> mojo.DepPath:
    """Return path to bunny2.stl mesh file."""
    mesh_path = MESHES_DIR / "bunny2.stl"
    assert mesh_path.exists(), f"Mesh file not found: {mesh_path}"
    return mesh_path


@pytest.fixture
def bunny_mesh_file() -> mojo.DepPath:
    return _bunny_mesh_file()


def _ball_mesh_file() -> mojo.DepPath:
    """Return path to ball.stl mesh file."""
    mesh_path = MESHES_DIR / "ball.stl"
    assert mesh_path.exists(), f"Mesh file not found: {mesh_path}"
    return mesh_path


@pytest.fixture
def ball_mesh_file() -> mojo.DepPath:
    return _ball_mesh_file()


def _cup_mesh_file() -> mojo.DepPath:
    """Return path to cup.stl mesh file."""
    mesh_path = MESHES_DIR / "cup.stl"
    assert mesh_path.exists(), f"Mesh file not found: {mesh_path}"
    return mesh_path


@pytest.fixture
def cup_mesh_file() -> mojo.DepPath:
    return _cup_mesh_file()


def _model_with_geoms(
    _ball_mesh_file: mojo.DepPath,
    _cup_mesh_file: mojo.DepPath,
    _bunny_mesh_file: mojo.DepPath,
) -> ModelWithGeoms:
    meshes: list[mojo.AnyMesh] = [
        ball_mesh := mojo.Mesh(
            name=mojo.MeshName("ball_mesh"),
            file=_ball_mesh_file,
            scale=np.ones(3) * 0.5,
        ),
        bunny_mesh := mojo.Mesh(
            name=mojo.MeshName("bunny_mesh"),
            file=_bunny_mesh_file,
            scale=np.ones(3) * 2,
        ),
        cup_mesh := mojo.Mesh(
            name=mojo.MeshName("cup_mesh"),
            file=_cup_mesh_file,
        ),
    ]
    assert ball_mesh.name and cup_mesh.name and bunny_mesh.name

    cup = mojo.Body(
        name=mojo.BodyName("cup_body"),
        pose=mojo.PoseQuat(pos=np.array((0.0, 0.0, 0.0))),
        geoms=[
            cup_geom := mojo.GeomMesh(
                name=mojo.GeomName("cup_geom"),
                mesh=cup_mesh.name,
                rgba=mojo.utils.Color.CYAN_500.with_alpha(0.2),
            )
        ],
    )

    bunny_in_cup = mojo.Body(
        name=mojo.BodyName("bunny_in_cup"),
        pose=mojo.PoseQuat(pos=np.array((0.0, 0.3, 1.0))),
        geoms=[
            bunny_in_cup_geom := mojo.GeomMesh(
                name=mojo.GeomName("bunny_in_cup_geom"),
                mesh=bunny_mesh.name,
                rgba=mojo.utils.Color.ROSE_500.rgba,
            )
        ],
    )

    bunny_below_cup = mojo.Body(
        name=mojo.BodyName("bunny_below_cup"),
        pose=mojo.PoseQuat(pos=np.array((0.0, 0.0, -1.0))),
        geoms=[
            bunny_below_cup_geom := mojo.GeomMesh(
                name=mojo.GeomName("bunny_below_cup_geom"),
                mesh=bunny_mesh.name,
                rgba=mojo.utils.Color.AMBER_500.rgba,
            )
        ],
    )

    ball_above_cup = mojo.Body(
        name=mojo.BodyName("ball_above_cup"),
        pose=mojo.PoseQuat(pos=np.array((0.0, 0.0, 2.3))),
        geoms=[
            ball_above_cup_geom := mojo.GeomMesh(
                name=mojo.GeomName("ball_above_cup_geom"),
                mesh=ball_mesh.name,
                rgba=mojo.utils.Color.EMERALD_500.rgba,
            )
        ],
    )

    mujoco_mjcf = mojo.Mujoco(
        options=[mojo.Option(timestep=0.001, gravity=np.array((0.0, 0.0, -9.81)))],
        worldbody=mojo.WorldBody(
            bodies=[cup, bunny_in_cup, bunny_below_cup, ball_above_cup]
        ),
        assets=[mojo.Asset(meshes=meshes)],
    )

    # compile and forward sim to add bounding spheres in correct location
    mj_model, mj_data = mujoco_mjcf.prep_for_sim()
    _rgba = mojo.utils.Color.WHITE.with_alpha(0.05)

    viz_targets = [
        (cup_geom, cup.name),
        (bunny_in_cup_geom, bunny_in_cup.name),
        (bunny_below_cup_geom, bunny_below_cup.name),
        (ball_above_cup_geom, ball_above_cup.name),
    ]

    bounding_spheres: list[mojo.AnySite] = []
    for geom, b_name in viz_targets:
        rad, local_centroid = geom.vertex_max_norm(mj_model)
        world_centroid = geom.rt_xpos(mj_model, mj_data) + (
            geom.rt_xmat(mj_model, mj_data) @ local_centroid
        )
        bounding_spheres.append(
            mojo.SiteSphere(
                name=mojo.SiteName(f"{b_name}_bounding_sphere"),
                size=rad,
                rgba=_rgba,
                pose=mojo.PoseQuat(pos=world_centroid),  # Centered on the volume
            )
        )

    assert mujoco_mjcf.worldbody
    mujoco_mjcf.worldbody.sites = bounding_spheres

    return ModelWithGeoms(
        mujoco_model=mujoco_mjcf,
        bunny_in_cup_geom=bunny_in_cup_geom,
        bunny_below_cup_geom=bunny_below_cup_geom,
        ball_above_cup_geom=ball_above_cup_geom,
        cup_geom=cup_geom,
    )


@pytest.fixture
def model_with_geoms(
    ball_mesh_file: mojo.DepPath,
    cup_mesh_file: mojo.DepPath,
    bunny_mesh_file: mojo.DepPath,
) -> ModelWithGeoms:
    return _model_with_geoms(ball_mesh_file, cup_mesh_file, bunny_mesh_file)


def _compiled_model(_model_with_geoms: ModelWithGeoms) -> CompiledModel:
    """Compile model and create MuJoCo data, returning geom references too."""
    return CompiledModel.from_model_with_geoms(_model_with_geoms)


@pytest.fixture
def compiled_model(model_with_geoms: ModelWithGeoms) -> CompiledModel:
    """Compile model and create MuJoCo data, returning geom references too."""
    return _compiled_model(model_with_geoms)


# ============================================================================
# Basic Functionality Tests
# ============================================================================


def test_proximity_type_enum():
    """Test mojo.ProximityType enum values."""
    assert mojo.ProximityType.SPHERE_TO_SPHERE == 0
    assert mojo.ProximityType.CONVEX_HULL == 1
    assert mojo.ProximityType.VERTEX_TO_FACE == 3
    assert mojo.ProximityType.FACE_TO_FACE == 4

    # Test enum names
    assert mojo.ProximityType.SPHERE_TO_SPHERE.name == "SPHERE_TO_SPHERE"
    assert mojo.ProximityType.CONVEX_HULL.name == "CONVEX_HULL"


# ============================================================================
# Proximity Calculation Tests
# ============================================================================


def force_sphere_to_sphere(
    compiled_model: CompiledModel, algorithm: mojo.ProximityType
):
    dist, _p1, _p2, prox_type = mojo.utils.Proximity(
        geom_1=compiled_model.cup_geom,
        geom_2=compiled_model.bunny_in_cup_geom,
        dist_max=-np.inf,
        algorithm=algorithm,
    ).get_proximity(compiled_model.mj_model, compiled_model.mj_data)
    assert isinstance(dist, (float, np.floating))
    assert dist >= 0.0
    assert prox_type == mojo.ProximityType.SPHERE_TO_SPHERE


def test_convex_hull_proximity(compiled_model: CompiledModel):
    """Test convex hull proximity calculation."""
    proximity = mojo.utils.Proximity(
        geom_1=compiled_model.bunny_in_cup_geom,
        geom_2=compiled_model.cup_geom,
        dist_max=1.0,
    )

    dist, p1, p2, prox_type = proximity.get_convex_hull_proximity(
        compiled_model.mj_model, compiled_model.mj_data
    )

    assert isinstance(dist, (float, np.floating))
    assert p1.shape == (3,)
    assert p2.shape == (3,)
    assert prox_type == mojo.ProximityType.CONVEX_HULL


def test_vertex_to_face_proximity(compiled_model: CompiledModel):
    """Test vertex-to-face proximity calculation."""
    proximity = mojo.utils.Proximity(
        geom_1=compiled_model.bunny_in_cup_geom,
        geom_2=compiled_model.cup_geom,
        dist_max=1.0,
    )

    # Test with fromto
    dist, p1, p2, prox_type = proximity.get_vertex_to_face_proximity(
        compiled_model.mj_model, compiled_model.mj_data
    )

    assert isinstance(dist, (float, np.floating))
    assert p1.shape == (3,)
    assert p2.shape == (3,)
    assert prox_type == mojo.ProximityType.VERTEX_TO_FACE


def test_face_to_face_proximity(compiled_model: CompiledModel):
    """Test face-to-face proximity calculation."""
    proximity = mojo.utils.Proximity(
        geom_1=compiled_model.bunny_in_cup_geom,
        geom_2=compiled_model.cup_geom,
        dist_max=1.0,
    )

    # Test with fromto
    dist, p1, p2, prox_type = proximity.get_face_to_face_proximity(
        compiled_model.mj_model, compiled_model.mj_data
    )
    assert isinstance(dist, (float, np.floating))
    assert p1.shape == (3,)
    assert p2.shape == (3,)
    assert prox_type == mojo.ProximityType.FACE_TO_FACE


def test_sphere_to_sphere_proximity(compiled_model: CompiledModel):
    """Test sphere-to-sphere (broadphase only) proximity calculation."""
    proximity = mojo.utils.Proximity(
        geom_1=compiled_model.bunny_in_cup_geom,
        geom_2=compiled_model.cup_geom,
        dist_max=1.0,
        algorithm=mojo.ProximityType.SPHERE_TO_SPHERE,
    )

    # Test with fromto
    dist, p1, p2, prox_type = proximity.get_proximity(
        compiled_model.mj_model, compiled_model.mj_data
    )
    assert isinstance(dist, (float, np.floating))
    assert p1.shape == (3,)
    assert p2.shape == (3,)
    assert prox_type == mojo.ProximityType.SPHERE_TO_SPHERE


def test_get_proximity_dispatcher(compiled_model: CompiledModel):
    """Test get_proximity dispatcher method."""
    # Test each algorithm type returns correct mojo.ProximityType
    for algo in list(mojo.ProximityType):
        proximity = mojo.utils.Proximity(
            geom_1=compiled_model.bunny_in_cup_geom,
            geom_2=compiled_model.cup_geom,
            dist_max=1.0,
            algorithm=algo,
        )
        dist, p1, p2, prox_type = proximity.get_proximity(
            compiled_model.mj_model, compiled_model.mj_data
        )
        assert prox_type == algo, (
            f"{algo.name}: returned prox_type ({prox_type.name}) does not match commanded {algo.name}"
        )
        assert isinstance(dist, (float, np.floating))
        assert dist >= 0.0
        assert p1.shape == (3,)
        assert p2.shape == (3,)


def test_proximity_reciprocity(compiled_model: CompiledModel):
    """
    Test that A -> B distance is identical to B -> A distance, and that contact points (p1, p2) are correctly swapped.
    """
    geom_a = compiled_model.bunny_below_cup_geom
    geom_b = compiled_model.cup_geom
    for algo in list(mojo.ProximityType):
        # Query A to B
        dist_ab, p1_ab, p2_ab, _ = mojo.utils.Proximity(
            geom_1=geom_a,
            geom_2=geom_b,
            dist_max=10.0,
            algorithm=algo,
        ).get_proximity(
            mj_model=compiled_model.mj_model, mj_data=compiled_model.mj_data
        )

        # Query B to A
        dist_ba, p1_ba, p2_ba, _ = mojo.utils.Proximity(
            geom_1=geom_b,
            geom_2=geom_a,
            dist_max=10.0,
            algorithm=algo,
        ).get_proximity(
            mj_model=compiled_model.mj_model, mj_data=compiled_model.mj_data
        )

        # Assert Distance Reciprocity
        assert dist_ab == pytest.approx(dist_ba), (
            f"{algo.name}: Distance is not reciprocal! A->B: {dist_ab}, B->A: {dist_ba}"
        )

        # Assert Point Reciprocity
        # p1 on A (A->B) must match p2 on A (B->A)
        # p2 on B (A->B) must match p1 on B (B->A)
        assert np.allclose(p1_ab, p2_ba, atol=1e-7), (
            f"{algo.name}: Contact points not swapped correctly for p1. p1_ab: {p1_ab}, p2_ba: {p2_ba}"
        )
        assert np.allclose(p2_ab, p1_ba, atol=1e-7), (
            f"{algo.name}: Contact points not swapped correctly for p2. p2_ab: {p2_ab}, p1_ba: {p1_ba}"
        )


# ============================================================================
# Broadphase Cutoff Tests
# ============================================================================


def test_broadphase_cutoff(compiled_model: CompiledModel):
    """Test that broadphase cutoff (dist_max) works correctly."""
    for algo in list(mojo.ProximityType):
        force_sphere_to_sphere(compiled_model, algo)


# ============================================================================
# Algorithm Comparison Tests
# ============================================================================


def test_algorithm_distance_ordering(compiled_model: CompiledModel):
    """
    Test that different proximity algorithms produce consistent relative distances.

    Generally, stricter algorithms (vertex-to-face, face-to-face) should produce larger or equal distances compared to broader approximations (sphere-to-sphere, convex hull).
    """
    # Get distances from all algorithms
    results: dict[mojo.ProximityType, float] = {}
    for algo in list(mojo.ProximityType):
        dist, p1, p2, prox_type = mojo.utils.Proximity(
            geom_1=compiled_model.bunny_below_cup_geom,
            geom_2=compiled_model.bunny_in_cup_geom,
            dist_max=10.0,
            algorithm=algo,
        ).get_proximity(
            compiled_model.mj_model,
            compiled_model.mj_data,
        )
        assert prox_type == algo, (
            f"{algo.name}: returned prox_type ({prox_type.name}) does not match commanded {algo.name}"
        )
        assert dist >= 0
        assert p1.shape == (3,)
        assert p2.shape == (3,)
        results[algo] = float(dist)

    # Sort by algo.value then check for monotonically increasing
    sorted_results = sorted(results.items(), key=lambda x: x[0].value)
    for i in range(len(sorted_results) - 1):
        current_algo, current_dist = sorted_results[i]
        next_algo, next_dist = sorted_results[i + 1]

        assert next_dist >= current_dist, (
            f"Accuracy Hierarchy Violation: {next_algo.name} ({next_dist}) is less than {current_algo.name} ({current_dist})."
        )
        # this is mainly a rule of thumb, i dont know how long I will keep this test


def test_fromto_returns_valid_points(compiled_model: CompiledModel):
    """Test that fromto parameter returns valid closest points."""
    # Test each algorithm with fromto=True
    for algo in list(mojo.ProximityType):
        dist, p1, p2, prox_type = mojo.utils.Proximity(
            geom_1=compiled_model.bunny_below_cup_geom,
            geom_2=compiled_model.cup_geom,
            dist_max=np.inf,
            algorithm=algo,
        ).get_proximity(compiled_model.mj_model, compiled_model.mj_data)

        assert prox_type == algo, (
            f"{algo.name}: returned prox_type ({prox_type.name}) does not match commanded {algo.name}"
        )
        # Verify points are valid (not NaN)
        assert not np.any(np.isnan(p1)), f"{algo.name}: p1 contains NaN {p1=}"
        assert not np.any(np.isnan(p2)), f"{algo.name}: p2 contains NaN {p2=}"

        # Verify points have correct shape
        assert p1.shape == (3,), f"{algo.name}: p1 has wrong shape {p1=}"
        assert p2.shape == (3,), f"{algo.name}: p2 has wrong shape {p2=}"

        # Distance should be non-negative
        assert dist >= 0, f"{algo.name}: distance is negative {dist=}"


# ============================================================================
# Mesh Data Extraction Tests
# ============================================================================


def test_local_verts_faces_extraction(compiled_model: CompiledModel):
    """Test that local vertices and faces are correctly extracted from mesh."""
    # Bake proximity to extract mesh data
    compiled_model.bunny_in_cup_geom.bake_proximity(
        compiled_model.mj_model, mojo.ProximityType.VERTEX_TO_FACE
    )

    # Verify extracted data
    assert compiled_model.bunny_in_cup_geom._local_verts is not None
    assert compiled_model.bunny_in_cup_geom._local_faces is not None

    verts = compiled_model.bunny_in_cup_geom._local_verts
    faces = compiled_model.bunny_in_cup_geom._local_faces

    # Check shapes
    assert verts.ndim == 2
    assert verts.shape[1] == 3, "Vertices should be 3D points"
    assert len(verts) > 0, "Mesh should have vertices"

    assert faces.ndim == 2
    assert faces.shape[1] == 3, "Faces should be triangles"
    assert len(faces) > 0, "Mesh should have faces"

    # Verify face indices are within vertex range
    max_vertex_idx = verts.shape[0]
    assert np.all(faces < max_vertex_idx), "Face indices out of bounds"
    assert np.all(faces >= 0), "Face indices should be non-negative"


def test_baked_mesh_properties(compiled_model: CompiledModel):
    """Test that baked trimesh has correct properties."""
    # Bake proximity
    compiled_model.bunny_in_cup_geom.bake_proximity(
        compiled_model.mj_model, mojo.ProximityType.VERTEX_TO_FACE
    )

    # Check trimesh properties
    mesh = compiled_model.bunny_in_cup_geom._baked_mesh
    assert mesh is not None
    assert len(mesh.vertices) > 0
    assert len(mesh.faces) > 0

    # trimesh uses 'is_empty' to signal a mesh with no geometry
    assert not mesh.is_empty, "Trimesh should contain geometry"

    # If you want to be extra thorough about MuJoCo-compatible geometry:
    assert mesh.is_winding_consistent, "Mesh faces should have consistent orientation"


# ============================================================================
# Caching Tests
# ============================================================================


def test_proximity_caching(compiled_model: CompiledModel):
    """Test that proximity calculations are cached properly."""
    proximity = mojo.utils.Proximity(
        geom_1=compiled_model.bunny_in_cup_geom,
        geom_2=compiled_model.cup_geom,
        dist_max=10.0,
    )
    # First call should bake
    assert compiled_model.bunny_in_cup_geom._baked_query is None
    dist1, _p1, _p2, _ = proximity.get_vertex_to_face_proximity(
        compiled_model.mj_model, compiled_model.mj_data
    )

    # After first call, should be cached
    assert compiled_model.bunny_in_cup_geom._baked_query is not None

    # Second call should use cache
    dist2, _p1, _p2, _ = proximity.get_vertex_to_face_proximity(
        compiled_model.mj_model, compiled_model.mj_data
    )

    # Results should be identical
    assert np.isclose(dist1, dist2)


def test_radius_caching(compiled_model: CompiledModel):
    """Test that bounding radius is cached."""
    # Initially NaN
    assert np.isnan(compiled_model.bunny_in_cup_geom._rad)

    # After baking, should be set
    compiled_model.bunny_in_cup_geom.bake_proximity(
        compiled_model.mj_model, mojo.ProximityType.CONVEX_HULL
    )
    assert not np.isnan(compiled_model.bunny_in_cup_geom._rad)
    assert compiled_model.bunny_in_cup_geom._rad > 0

    cached_rad = compiled_model.bunny_in_cup_geom._rad

    # After another bake, should remain the same
    compiled_model.bunny_in_cup_geom.bake_proximity(
        compiled_model.mj_model, mojo.ProximityType.CONVEX_HULL
    )
    assert compiled_model.bunny_in_cup_geom._rad == cached_rad


if __name__ == "__main__":
    ball_path = _ball_mesh_file()
    cup_path = _cup_mesh_file()
    bunny_path = _bunny_mesh_file()

    print(f"Loading meshes from: {ball_path.parent}")

    model_desc = _model_with_geoms(ball_path, cup_path, bunny_path)
    model = _compiled_model(model_desc)

    print("Model compiled successfully. Running proximity test...")

    # test_convex_hull_proximity(model)
    # test_vertex_to_face_proximity(model)
    # test_face_to_face_proximity(model)
    # test_sphere_to_sphere_proximity(model)
    # test_get_proximity_dispatcher(model)
    # test_invalid_proximity_algorithm_raises_error(model)
    # test_broadphase_cutoff(model)
    # test_algorithm_distance_ordering(model)
    test_fromto_returns_valid_points(model)
    # test_local_verts_faces_extraction(model)

    print("Test complete.")
