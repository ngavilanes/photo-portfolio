# Lesson roadmap

One lesson a week. Each lesson takes a technique found in a breakdown, gives you a shot list
for the a6700, the Resolve Studio steps, and the common mistakes. You shoot it, cut it, and we
compare it with the reference.

The first six come from `references/airports/`. The order follows what the measurements showed
this editor actually relies on, rather than the order I first guessed.

| # | Technique | Evidence from the breakdown | Resolve tools |
|---|---|---|---|
| 01 | **Cutting on the beat and half-beat** | 7 of 9 cuts within ±70 ms of a beat or half-beat at 161.5 bpm | Markers (`M`), snapping, Ripple Trim, Fairlight waveform zoom |
| 02 | **Object white-out flashes on the beat** | 6 single-object white flashes of 2-3 frames each. 5 of 6 land within ±34 ms of a beat or half-beat | Magic Mask (Studio) or a tracked Power Window, then Gain to white with a 2-frame keyframe |
| 03 | **Flash frames that cover cuts** | From the 60 fps hand review: a white flash at 6.55s after a zoom-blur ramp, and an over-saturated cyan flash at 9.43s. The tool currently folds these into plain hard cuts | Adjustment clip, Offset/Gain flash, Transform zoom with motion blur |
| 04 | **The teal grade** | 6 of 10 shots read "green tint", 2 desaturated, saturation 0.16-0.37, then a deliberate break to a magenta/purple sunset for the ending | Node tree: balance, then a look (Hue vs Hue, Offset), then a Group Post-Clip node |
| 05 | **Masked reveal and match cut** | Circular masks show the next shot's engines from 8.7s before the cut at 9.43s | Fusion: Ellipse mask + Merge, or a Color-page window with a tracker |
| 06 | **Composite and growing inset** | The woman is layered onto the plane plate at 10.24s, then a jet-bridge inset grows to full frame by 11.04s | Magic Mask or a Delta Keyer, Transform keyframes, Dynamic Zoom, a Crop border |

The hook was not one of the reel's strengths by the numbers: the first real cut is at 3.6s and it
loops through black. Worth discussing in lesson 01: what would you change to hold attention in the
first second?

Template: `templates/lesson.md`.
