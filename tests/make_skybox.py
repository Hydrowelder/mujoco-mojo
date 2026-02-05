from pathlib import Path

import numpy as np

import mujoco_mojo as mojo

worldbody = mojo.WorldBody()
mujoco = mojo.Mujoco(
    worldbody=worldbody,
    model=mojo.ModelName("skybox_model"),
    assets=[mojo.Asset()],
)

# Download this skybox from here: https://www.david-gable.com/work/photography/Space/Star-Skybox/p1/
cube_folder = mojo.DepPath() / "textures" / "stars"
mujoco.assets[0].textures.append(
    skybox_texture := mojo.Texture(
        name=mojo.TextureName("skybox_texture_colors"),
        type=mojo.TextureType.SKYBOX,
        fileback=cube_folder / "nz.png",
        filedown=cube_folder / "ny.png",
        filefront=cube_folder / "pz.png",
        fileleft=cube_folder / "nx.png",
        fileright=cube_folder / "px.png",
        fileup=cube_folder / "py.png",
    )
)

worldbody.bodies.append(
    mojo.Body(
        name=mojo.BodyName("box_body"),
        geoms=[mojo.GeomBox(size=np.array([0.5] * 3))],
    )
)
mujoco.write_xml(
    Path(__file__).with_name("model_with_skybox.xml"), exclude_default=True
)
