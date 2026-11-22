# Video Recording

!!! abstract

    **VideoRecorder** films any camera in your model while a run goes and saves the video in the trial's folder. It is the quickest way to check that a run did what you meant, and to show it to someone else.

    <figure markdown="span">
        <video autoplay controls muted loop playsinline width="80%">
            <source src="video-recording.mp4" type="video/mp4">
        </video>
        <figcaption>The example below, at half speed. The recorder switches on when the ball first comes within 0.6 m of the floor, and then keeps going. The violet line is the ball's trail.</figcaption>
    </figure>

    <!-- video-recording.mp4 is made by record_clip in video_recording_example.py: run that file to remake it (set MUJOCO_GL=egl if there is no display) -->

---

## Recording a Camera

A recorder films a camera that is named in the model. The camera can be fixed in the world, as here, or attached to a moving body, and then the video moves with that body. This model has a ball above a tilted wedge, so the ball bounces off sideways, a fixed camera beside the ball's path, and a spotlight overhead:

```python
--8<-- "docs/user-guides/features/video_recording_example.py:model"
```

To film it, make a [`VideoRecorder`][mujoco_mojo.runtime.video_recorder.VideoRecorder] inside the runtime function, call `setup` with the state, and `register_to_rm` so the [`RuntimeManager`][mujoco_mojo.runtime.runtime_manager.RuntimeManager] captures a frame as the run goes and saves the file when it finishes. It needs a `path`, a `camera_name` and a `frame_rate`, and the extension of the path picks the format:

=== "MP4"

    H.264 through ffmpeg, which has to be installed and on your `PATH`. It plays almost everywhere, so it is the safe choice when you do not know where the video will be watched.

    ```python
    --8<-- "docs/user-guides/features/video_recording_example.py:mp4"
    ```

=== "WebM"

    VP9 through ffmpeg, so the file is smaller than an MP4, and it is fully seekable in the Dojo viewer. It needs an ffmpeg with VP9 support.

    ```python
    --8<-- "docs/user-guides/features/video_recording_example.py:webm"
    ```

=== "GIF"

    Written with PIL, so it needs no ffmpeg. It loops, and the file is large. Every frame is held in memory until the run ends, and `max_frames` caps how many are taken.

    ```python
    --8<-- "docs/user-guides/features/video_recording_example.py:gif"
    ```

Only the MP4 records in the example. The WebM and the GIF are there to show their paths, so the example takes them out again with `unregister_from_rm`.

- `path` is where the video goes. The trial's folder, `mojo_model.trial_dir`, keeps each trial's video next to its telemetry, and the [Trial Details](dojo/trial-details.md) page of the Dojo plays it.
- `show_traces` draws the trail behind the ball, which is covered under [Overlays](#overlays).
- `frame_rate` is frames per unit of **simulation** time (seconds, unless your model uses another unit), so the same stretch of simulation is always the same number of frames however fast the run goes. `playback_speed` changes only how fast the saved video plays: 0.5 is slow motion, and 2 is double speed.

The recorders in the example also take a `recording_trigger` and a `frame_label`. Both are functions of the state, defined in the runtime function just above the recorders:

```python
--8<-- "docs/user-guides/features/video_recording_example.py:functions"
```

- `recording_trigger` makes the recorder only take frames while it returns `True`. This one latches on when the ball first comes within 0.6 m of the floor and stays on. A trigger that followed the ball's height instead would skip the top of every bounce, and the video would jump forward over each gap.
    - This is helpful to programmatically control when your recorder is active.

???+ tip "Tip: The Video Does Not Start at t = 0"

    The trigger stays off until the ball first comes within 0.6 m of the floor, so the first frame of the example video is at t = 0.43 s. The label shows the simulation time, so the start is easy to see.

- `frame_label` is a function of the state that returns the text to burn into the frame, along with optional `position`, `color`, `background_color` and `font_size` (a `LabelConfig`). Here it is the time and the height.

The recorder is made only in the nominal trial, `mojo_model.is_nominal`. A Monte Carlo job runs many trials, and filming every one would cost time and disk for videos nobody watches. The Reloaded `record` command also turns recording off (see [Reloaded](reloaded.md)).

---

## Overlays

A recorder can draw more than the camera sees. `show_proximities` draws the lines of your [Proximity](proximity.md) pairs, and `show_loads` draws the custom force arrows from your runtime script (see the [runtime script guide](../workflow/runtime-script.md#video-recording)).

`show_traces` draws trails. A [`Tracer`][mujoco_mojo.runtime.tracer.Tracer] follows a body, site or geom and keeps its recent path, and any recorder with `show_traces=True` draws that path behind it. The example traces the ball:

```python
--8<-- "docs/user-guides/features/video_recording_example.py:tracer"
```

???+ warning "Warning: Tracers Are Expensive"

    Avoid tracers if you can.

    A tracer records a point on every step, and a recorder redraws the whole trail on every frame. The cost grows with the length of the trail, which is its `duration` divided by the timestep.

    Filming 2 s of simulation in this example took:

    | Trail                            | Time   | Compared with no trail |
    | :------------------------------- | :----- | :--------------------- |
    | None                             | 0.22 s | baseline               |
    | 1 s                              | 0.60 s | 2.7 times slower       |
    | 5 s                              | 0.72 s | 3.3 times slower       |
    | 1 s, with `record_decimation=10` | 0.27 s | 1.2 times slower       |

    If you need a trail, keep `duration` short and raise `record_decimation`. These times are from a small scene, so yours will differ.

`duration` is how far back the trail reaches, and the trail fades toward its oldest end. `color` and `width` style it, and `record_decimation` records a point only every few steps, which keeps the trail short on a fine timestep. The default color is the `visualization.trace_line` setting.

---

## Picture Size

`width` and `height` set the size of the picture, and they default to 640 by 480. MuJoCo renders into an offscreen buffer that is also 640 by 480 unless the model says otherwise, so a recorder that asks for a larger picture raises a `ValueError` when `setup` runs, naming both sizes. If a higher resolution than standard definition is desired, you need to raise the buffer size in the generator like this:

```python
--8<-- "docs/user-guides/features/video_recording_example.py:offscreen"
```

This model makes room for 1280 by 720, so a recorder here can ask for `width=1280` and `height=720`.

---

## Size, Speed and Cost

A larger picture (see [Picture Size](#picture-size)) costs more to render and makes a larger file. `quality` and `encode_speed` tune the ffmpeg encoder for `.mp4` and `.webm`: a lower `quality` number is a better picture and a larger file, and a higher `encode_speed` is a faster encode and a worse compression. `.mp4` and `.webm` frames are sent to the encoder as they are captured, so a long run does not fill the memory.

Every frame is rendered on the thread that steps the simulation, so it costs wall time. On this small scene a frame took about 1.4 ms, and starting the encoder took about 50 ms once, while a physics step took about 15 microseconds. A bigger scene costs more per frame. The levers are `frame_rate`, the size, and recording only when you need to, with a trigger or only the nominal trial.

---

??? example "All Code"

    ```python
    --8<-- "docs/user-guides/features/video_recording_example.py:example"
    ```

---

!!! success

    You can now film any camera in your model, choose when it records and what the frames say, and keep the cost down.
