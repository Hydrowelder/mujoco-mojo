"""There are a lot of sensors. It would take a large amount of time to make them all by hand. So this script helps to template a file to copy many times."""

from pathlib import Path

template_text = Path(__file__).with_name("sensor_template.py").read_text()

sensor_attr_folder = (
    Path.cwd() / "src" / "mujoco_mojo" / "mjcf" / "mujoco_attr" / "sensor_attr"
)
assert sensor_attr_folder.is_dir()
assert sensor_attr_folder.exists()

paths = [
    sensor_attr_folder / p
    for p in Path(__file__).with_name("filestomake.txt").read_text().splitlines()
]

# for testing I throw out all but two
# paths = [paths[0], paths[1]]
for_init = []
for path in paths:
    name = path.stem

    # t = Template(template_text)
    # output = t.substitute(
    #     name_pascal=name.capitalize(),
    #     name_lower=name.lower(),
    # )
    # path.write_text(output)

    for_init.append({"name": name, "obj_name": f"Sensor{name.capitalize()}"})

# write __init__.py
init_top_str = ""
init_all_str = "__all__=[\n"

import_str = ""
for init in for_init:
    init_top_str += f"from .{init['name']} import {init['obj_name']}\n"
    init_all_str += f'"{init["obj_name"]}",\n'

    # make it faster to bulk import
    import_str += f"from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.{init['name']} import {init['obj_name']}\n"

init_all_str += "\n]"

init_str = init_top_str + init_all_str
# paths[0].with_stem("__init__").write_text(init_str)

print(import_str)
