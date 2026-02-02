Guide is coming soon...

!!! warning "Default Values"
    Some attributes in this package make use of default values. Wherever possible, the default values match what is stated in the [XML Reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html#xml-reference){:target="_blank"}. The `to_xml` method found in all `XMLModel` (which is most objects in `mujoco_mojo.mjcf`) has an argument (`exclude_defaults`) which will omit serializing fields set as default.

    If you have a specific use case which is dependent on a value you leave as default, it is highly recommended that you pin that value as opposed to use the default. MuJoCo may change their defaults, and this package may fall behind. In that case, you would be using a "default" which is no longer the default.

## Implemented MJCF Tags

??? "mujoco"
    * [x] mujoco
      * [x] option
          * [x] option/⁠flag
      * [x] compiler
          * [x] compiler/⁠lengthrange
      * [x] size
      * [x] statistic
      * [x] asset
          * [x] asset/⁠mesh
              * [x] mesh/⁠plugin
          * [x] asset/⁠hfield
          * [x] asset/⁠skin
          * [x] asset/⁠texture
          * [x] asset/⁠material
              * [x] material/⁠layer
          * [x] asset/⁠model
      * [x] (world)body
          * [x] body/⁠inertial
          * [x] body/⁠joint
          * [x] body/⁠freejoint
          * [x] body/⁠geom
              * [x] geom/⁠plugin
          * [x] body/⁠site
          * [x] body/⁠camera
          * [x] body/⁠light
          * [x] body/⁠composite
              * [x] composite/⁠joint
              * [x] composite/⁠geom
              * [x] composite/⁠site
              * [x] composite/⁠skin
              * [x] composite/⁠plugin
          * [x] body/⁠flexcomp
              * [x] flexcomp/⁠contact
              * [x] flexcomp/⁠edge
              * [x] flexcomp/⁠elasticity
              * [x] flexcomp/⁠pin
              * [x] flexcomp/⁠plugin
          * [x] body/⁠plugin
          * [x] body/⁠attach
          * [x] body/⁠frame
      * [x] contact
          * [x] contact/⁠pair
          * [x] contact/⁠exclude
      * [x] deformable
          * [x] deformable/⁠flex
              * [x] flex/⁠edge
              * [x] flex/⁠elasticity
              * [x] flex/⁠contact
          * [x] deformable/⁠skin
              * [x] skin/⁠bone
      * [x] equality
          * [x] equality/⁠connect
          * [x] equality/⁠weld
          * [x] equality/⁠joint
          * [x] equality/⁠tendon
          * [x] equality/⁠flex
          * [x] equality/⁠distance
      * [x] tendon
          * [x] tendon/⁠spatial
              * [x] spatial/⁠site
              * [x] spatial/⁠geom
              * [x] spatial/⁠pulley
          * [x] tendon/⁠fixed
              * [x] fixed/⁠joint
      * [x] actuator
          * [x] actuator/⁠general
          * [x] actuator/⁠motor
          * [x] actuator/⁠position
          * [x] actuator/⁠velocity
          * [x] actuator/⁠intvelocity
          * [x] actuator/⁠damper
          * [x] actuator/⁠cylinder
          * [x] actuator/⁠muscle
          * [x] actuator/⁠adhesion
          * [x] actuator/⁠plugin
      * [x] sensor
          * [x] sensor/⁠touch
          * [x] sensor/⁠accelerometer
          * [x] sensor/⁠velocimeter
          * [x] sensor/⁠gyro
          * [x] sensor/⁠force
          * [x] sensor/⁠torque
          * [x] sensor/⁠magnetometer
          * [x] sensor/⁠rangefinder
          * [x] sensor/⁠camprojection
          * [x] sensor/⁠jointpos
          * [x] sensor/⁠jointvel
          * [x] sensor/⁠tendonpos
          * [x] sensor/⁠tendonvel
          * [x] sensor/⁠actuatorpos
          * [x] sensor/⁠actuatorvel
          * [x] sensor/⁠actuatorfrc
          * [x] sensor/⁠jointactuatorfrc
          * [x] sensor/⁠tendonactuatorfrc
          * [x] sensor/⁠ballquat
          * [x] sensor/⁠ballangvel
          * [x] sensor/⁠jointlimitpos
          * [x] sensor/⁠jointlimitvel
          * [x] sensor/⁠jointlimitfrc
          * [x] sensor/⁠tendonlimitpos
          * [x] sensor/⁠tendonlimitvel
          * [x] sensor/⁠tendonlimitfrc
          * [x] sensor/⁠framepos
          * [x] sensor/⁠framequat
          * [x] sensor/⁠framexaxis
          * [x] sensor/⁠frameyaxis
          * [x] sensor/⁠framezaxis
          * [x] sensor/⁠framelinvel
          * [x] sensor/⁠frameangvel
          * [x] sensor/⁠framelinacc
          * [x] sensor/⁠frameangacc
          * [x] sensor/⁠subtreecom
          * [x] sensor/⁠subtreelinvel
          * [x] sensor/⁠subtreeangmom
          * [x] sensor/⁠insidesite
          * [x] collision sensors
          * [x] sensor/⁠distance
          * [x] sensor/⁠normal
          * [x] sensor/⁠fromto
          * [x] sensor/⁠contact
          * [x] sensor/⁠tactile
          * [x] sensor/⁠e_potential
          * [x] sensor/⁠e_kinetic
          * [x] sensor/⁠clock
          * [x] sensor/⁠user
          * [x] sensor/⁠plugin
      * [ ] keyframe
          * [ ] keyframe/⁠key
      * [ ] visual
          * [ ] visual/⁠global
          * [ ] visual/⁠quality
          * [ ] visual/⁠headlight
          * [ ] visual/⁠map
          * [ ] visual/⁠scale
          * [ ] visual/⁠rgba
      * [ ] default
          * [ ] default/⁠mesh
          * [ ] default/⁠material
          * [ ] default/⁠joint
          * [ ] default/⁠geom
          * [ ] default/⁠site
          * [ ] default/⁠camera
          * [ ] default/⁠light
          * [ ] default/⁠pair
          * [ ] default/⁠equality
          * [ ] default/⁠tendon
          * [ ] default/⁠general
          * [ ] default/⁠motor
          * [ ] default/⁠position
          * [ ] default/⁠velocity
          * [ ] default/⁠intvelocity
          * [ ] default/⁠damper
          * [ ] default/⁠cylinder
          * [ ] default/⁠muscle
          * [ ] default/⁠adhesion
      * [ ] custom
          * [ ] custom/⁠numeric
          * [ ] custom/⁠text
          * [ ] custom/⁠tuple
              * [ ] tuple/⁠element
      * [ ] extension
          * [ ] extension/⁠plugin
              * [ ] plugin/⁠instance
                  * [ ] instance/⁠config
