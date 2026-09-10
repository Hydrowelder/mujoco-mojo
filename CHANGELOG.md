# Changelog

## Version 2.6.9 (2026-09-10)

- Added support for MuJoCo 3.13.0
- Fixed transitive dependency issue warned by Dependabot
- Added changelog

## Version 2.6.8 (2026-09-09)

- Added a new example for the user guide based on my thesis research
- Removed many obsolete dependencies
    - Fixed Dependabot warnings
- Dojo Updates:
    - Added SensAI feature, which adds a chatbot to Dojo
        - This feature is still considered experimental
    - Added a system to allow multiple plots to be open at once via tabs, like in the Lab
    - Added a settings editor and upgraded folder-like elements to use a folder navigation system
    - Lots of style improvements and deep integration with tooltip helpers
    - Reworked Dojo to use a better color system (mainly helpful for development)
- Settings Updates:
    - Updated to add lots of new CLI settings
    - Settings now allow for project-specific settings
    - Replaced the original SLURM overrides JSON file
    - Project settings now take priority over Global settings
- Fixed asset bundling to use a folder structure, preventing files with the same name from being overwritten
    - Added an option to symlink instead of copy on POSIX systems
- Fixes for reloaded recording telemetry
- Updated the `Frame` class so it is actually useful
- Significant improvement to cold start time

## Version 2.6.7 (2026-08-26)

- Partial compatibility with MuJoCo v3.12.0
    - Added Orientation and PID actuators
    - Removed VND texture support
    - Updated DCMotor definition
- Updated defaults
- Fixed mesh builtins
- Updated developer MJCF schema checking tool to use the new schema published by MuJoCo developers
- Typing fixes and missing attrs

## Version 2.6.6 (2026-08-11)

- Fixed Dependabot warnings
- Fixed lost unit system

## Version 2.6.3 (2026-07-26)

- Added an option to quickly relaunch Reloaded in case the viewer crashes
- Fixed a bug with face-to-face proximity not clipping to zero
- Cached Tracer's per-segment `LineConfig` objects instead of rebuilding the whole trail on every render call
- Added more flexibility to the Slurm submission script to allow users to define global and per-job overrides using settings and/or a JSON file
- Fixes for macOS unit tests

## Version 2.6.0 (2026-07-03)

- Added requirements feature allowing for automatic run analysis to alert users to specification failures
    - Allows for latching to prevent re-evaluation when it doesn't matter
- Added pinned trials option in Dojo
- Moved rotation feature calculations from `DataFrame` to `RotationFilter`
- Added downsampling, bulk unit conversions, and metadata display to Dojo
- Added model unit system feature
    - Telemetry signals now have a metadata option to include extra information about each column
    - Includes info for dimensional analysis and automatic unit conversion
    - Dojo now shows units (if known) and automatically hints a unit conversion in the quick filter if it's known
- Loads can now have their lengths and widths scaled independently for force and torque
- Fixed a bug where `reset_rng` worked backwards

## Version 2.5.7 (2026-06-26)

- Model config name is no longer required. It will not be written by default.
- Fixed a bug where the `SignalManager` buffer did not flush due to a Windows file lock
    - `SignalManager` now writes partial Parquet files (up to 8 MB/user defined)
    - When `close()` is called (such as when a runtime manager context closes), the partials are read back in and stitched together
- Added Coulomb joint friction
- Added new requests for actuators and joints
- Renamed `ActuatorLoad` to `ActuatorControl`
- MP4 and WebM videos are now streamed to disk rather than saved in the frame buffer, which saves memory
- Ensured FFmpeg is installed for CI

## Version 2.5.6 (2026-06-24)

- Improved labeling for video recording
- Updated test to use EGL mode for rendering during tests
- Removed ballscrew. Added loads to `__all__`
- Added missing `__init__` imports

## Version 2.4.5 (2026-06-23)

- Added tracer mode so you can see how a site/traceable type moves through the sim
- Now writing stochas folder in Reloaded too
- Fixed a bug where a missing signal manager just raised an error
- Added `RuntimeManager` and `SignalManager` context managers system
    - Updated docs to reflect this
- Added actuator loads

## Version 2.4.4 (2026-06-21)

- Fixes for when named values are lists instead of single values
- Added caching for proximities within a single timestep
- Fixed a Windows bug where running `dojo.sh` prevented workdir cleanup on a rerun
- Added a developer tool to periodically check the official XML reference documentation to compare against the `mjcf` module objects. Caught a bunch of errors right off the bat.
- Added a check to warn the user if the video recorder requests a higher resolution than the offscreen renderer is configured for
- Added additional checks to make sure XML attributes are always present. Fixed missing `Joint` and other classes missing attributes list

## Version 2.4.3 (2026-06-16)

- Added a distribution viewer to see where a given trial's named values fit within the distribution
    - Now reports the stochas distributions in the workdir along with the categorical tables for report generation
- Fixed missing `AnyDist`

## Version 2.4.1 (2026-06-14)

- Added warning when proximity calculations are being discarded (potentially by accident, as the calculation is expensive)
- Updates for Reloaded to allow early termination, printing Dojo, and better dark mode for viser
- `Inertial` now has an option to avoid resetting the RNG
- Slurm submission fixes and added throttle argument

## Version 2.3.10 (2026-06-13)

- Added plot resizing handle
- Dojo no longer writes to the job status file
- Added schema validation, better marker behavior, and better shape/note editing
- Added new filters: `First`, `Last`, `Sort`, and `Reverse`
- Fixed bugs where rotations didn't work
- Added the rotation filter as an option in the signal Lab

## Version 2.3.9 (2026-06-12)

- Added JSON logging for each trial
- Added logs section in trial viewer

## Version 2.3.8 (2026-06-12)

- Upgraded `VideoRecorder` to allow for different playback speeds, recording triggers, frame labels, and max frames
    - Now closes the MuJoCo Renderer when the `RuntimeManager` context manager closes
- Updated images on the docs site. Added a new section to README
- Added UUID to prevent Dojo from hanging on to old job status files
- Prevented unpicklable parameters from being serialized when leaving multiprocessing
- Fixed the `select_attribute()` method so that it actually selects attributes
- Added a command to allow tracking a single float easily
- Added triangle inequality check to `Inertial`

## Version 2.3.7 (2026-06-09)

- Bug fix for dynamically reloading imported packages
- Added matrix rain and new logo print

## Version 2.3.6 (2026-06-07)

- Rewrote the Signal Lab's dirty-state and undo system to fix bugs where unsaved-change detection was wrong or stuck
- Added new statistics filter (min, max, mean, etc.)
- Updated Reloaded to work more like the regular runner to prevent drift

## Version 2.3.5 (2026-06-03)

- Added request options for contact forces
- Added Pose Context to allow elements to be added anywhere in the kinematic tree. Now also supports friction forces/torques

## Version 2.3.4 (2026-06-01)

- Fixed paths for Windows

## Version 2.3.3 (2026-05-31)

- Converted to `MjState` for `MjModel` and `MjData`
- Updated to use `UserData` class in loads instead of hodgepoged callable args
- Added visualization configuration and fixed some load bugs

## Version 2.3.2 (2026-05-30)

- Added tabs to Lab so you can edit multiple labs at a time
- Added ability to save a lab as a template to be used later as a single node
    - Allows complex filters to be reused in different scenarios and single units of complex groups to be tested more easily

## Version 2.3.1 (2026-05-29)

- Added settings that are saved to `~/.mujoco-mojo/settings.toml`
- Added an animation viewer to Dojo
    - Shows frame markers on plot
    - Includes playback speed options
- Added trial status to trial viewer
- Added `watchfiles` to enable auto-refreshing on file saves in Reloaded

## Version 2.3.0 (2026-05-24)

- Added a basic signal editor called Lab to Dojo
    - This new feature allows you to create custom signals **after** a run has completed
    - Uses a graph system to connect filters and signals together
    - Allows plotting of the new signal (note that these are in-memory only, not persisted to the DataFrame)
    - Includes auto-arrange and fit view
- Can now integrate or differentiate with respect to a signal rather than just Riemann integration
- Added option to apply filters to the X-axis
- Added polar chart option in trial viewer
- Added fullscreen button to all Dojo pages
- Fixed DataFrame namespace so you can chain methods without losing type hints
- Fixed double click, added Plotly notifications, improved shape editor with color selector, added better keyboard shortcuts, and improved profile saving (validation, session sharing, directories)

## Version 2.2.3 (2026-05-20)

- Added an `init` command to start fresh projects
- Now renumbering trial numbers on a trial expansion
- Updated docs to include an API reference

## Version 2.2.2 (2026-05-19)

- Added profile saving for configurations that users like and want to persist between sessions
- Added a notification history and more toast messages
- Unapplied changes are stored in a draft state
- Refactored Dojo to use TypeScript, a semantic CSS design system, and template partials

## Version 2.2.1 (2026-05-17)

- Added the ability to create custom meshes using `trimesh`. Also added constructors for frustums and boxes

## Version 2.2.0 (2026-05-10)

- Significant performance improvement for `SignalManager`
    - Switched to a contiguous memory buffer for signal recording and cached column names to avoid string composition on every loop
    - Dropped support for Pydantic models in recording to increase speed
- Added a new proximity system to determine minimum distance between geometries
    - Also supports concave hulls (not used for contacts)
- Added support for proximity visualization in Reloaded
- Fixes for thread safety

## Version 2.1.1 (2026-05-02)

- Added Hatch as a dev dependency
- Added support for Python 3.14 and MuJoCo v3.8.0

## Version 2.1.0 (2026-05-02)

- Added a new DataFrame wrapper for supercharged data analysis
    - Works as a namespace with Polars, allowing for Mojo methods while avoiding having to cast back to a `MojoFrame` every time
- Simplified `MojoFrame` so it includes the method to create a new instance from itself
- Added a `UnitFilter`, which allows users to easily switch column units
- Added Savitzky-Golay (savgol) filter

## Version 2.0.4 (2026-05-01)

- Completed the tennis racket theorem example
- Refined nomenclature
- Added a method to walk through bodies recursively
- Fully renamed `ResultManager` to `SignalManager` to prevent confusion with `RuntimeManager`
- Fixes to the `rt_inertia_world` method
- Assets will only copy when changed

## Version 2.0.3 (2026-04-29)

- Added the ability to run a Reloaded session from a model config file
- Handoff data is serialized using the new `mojo.UserData` class

## Version 2.0.1 (2026-04-20)

- Support for new stochas distributions

## Version 2.0.0 (2026-04-19)

- Added optimization toolkit
- Added user guide and new arguments for optimizer
- Additional stability for thread-safe operations
- Added the ability to view `optuna-dashboard` inside Dojo

## Version 1.7.6 (2026-04-17)

- Added a method to create an orientation from a rotation object
- Switched to using Parquet instead of DuckDB for signal outputs
- Updated to match MuJoCo v3.7.0 and updated dependency
    - Added DCMotor to actuator class
    - Added support for DCMotor

## Version 1.7.5 (2026-04-16)

- Added resolution download options for plots
- Built basic line editor dropdown

## Version 1.7.4 (2026-04-13)

- Added a chip to Dojo to indicate whether a live connection is present
- Converted `Mesh` to a discriminated union type
- Added new matrix types and improved the initial velocity setter

## Version 1.7.2 (2026-04-12)

- Added user guides on how to use MuJoCo Mojo to the docs
- Fixed asset links to be relative instead of absolute

## Version 1.7.1 (2026-04-11)

- Added load arrows to the `mjviser` viewer
    - *Note: They appear to be centered at the wrong location due to the world origin being misplaced.*
- Force and torque arrows now appear in the OpenGL viewer (same as when rendering a video)
- Added playback speed options to Reloaded
    - Incorporated runtime into Reloaded. Users can now playback generation and runtime in the viewer
- Added option to use `MjViewer` for the web viewer (in case X11 is unavailable)

## Version 1.7.0 (2026-04-10)

- Added `mujoco-mojo reloaded`, allowing you to run a script that automatically reloads a view of your model while you edit
- Added ability to change the reference frame for valid quaternions in Dojo
- Defaults to returning a quaternion instead of a full rotation matrix

## Version 1.6.0 (2026-04-08)

- Dojo updates:
    - Added password protection option for the site as well as an error page
    - Added polish to shapes by showing the active mode on the button, adding a cancel button, and adding a label option
- Added toggle option for equalities to allow simple runtime modification
- Added Geom output options

## Version 1.5.0 (2026-04-05)

- Added a shape and annotation configurer to Dojo
- Improved formatting and highlighting of errors in JSON
- Added undo/redo feature to Dojo trial viewer
- Added unit tests
- Static typing no longer requires as many `np.asarray` checks
- Added coordinate system tools expanding both `Pose` and `Orientations`

## Version 1.3.5 (2026-04-03)

- Added a system for outputting simulation data
- Added a new system for using custom forcing functions without needing to edit MuJoCo buffers
- Added support for a new video recording feature
- Added helper methods for generating custom inertia from random draws, addition, and subtraction
- Added a method to set the initial velocity condition of bodies
- Added a method to get the runtime center of mass of multiple bodies
- Added a method to use defined cameras as "recorders" at runtime
- New dashboard features:
    - Renamed dashboard to `Dojo`
    - `Mosaic`: Plot result data in an interactive viewer
    - Added ability to add filters or plot against many trials at once
    - Added buttons for easier customization
    - Uses a JSON format as the source of truth for simple saving and detailed editing
    - Plot views can be shared with other users via a web URL
    - Mobile support
    - Keyboard shortcuts for easier navigation
    - Confetti!
- Updated to new stochas package
- Theming updates to dashboard
- Fixed logging on Windows
- Dashboard performance improvements
- Added color utilities
- Added ability to submit jobs with Slurm

## Version 1.1.0 (2026-03-03)

- Added a basic dashboard to monitor job execution status
- Updated CLI to use `typer`
- Added a system to perform Monte Carlo studies with parallel execution support
- Added a run summary file that can be used as a lightweight alternative to the dashboard
- Added a method to decompose a mesh into multiple meshes, allowing non-convex volumes to be used
- Fixed XML generation so tuples export correctly
- Fixed `resume` functionality (previously the registry was overwritten with only finished runs, omitting runs lacking a status file)
- Raised exceptions now include tracebacks
- Fixed local time zone conversion differences between Windows and Linux handling
    - Dashboard and reports now use time zone abbreviations
- Added option to run specific trial numbers
- Added dependency asset handling via `DepPath`
    - Dependency assets now have an option to remap their location to a shared asset folder
    - Allows multiple trials to pull from the same dependency location to save storage space while keeping the workdir portable
- Added `mjtObj` attribute to named classes
- Fixed job status updating and querying

## Version 1.0.0 (2026-02-04)

- Initial release of `mujoco-mojo` with support for nearly the full MJCF definition
- Generates XML files using Pydantic classes for type safety
- Serialized XML is compact because default values are ignored (relying on MuJoCo default behavior)
- Documented objects to describe how MuJoCo interprets them
