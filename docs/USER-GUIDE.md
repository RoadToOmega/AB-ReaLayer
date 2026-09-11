# AB ReaLayer — Milestone 11 (0.11.1)

A multilayer random variation sampler for REAPER, built as a self-contained JSFX. Each WAV can contain
multiple variations. Detection separates them into regions; MIDI chooses a new
region according to each layer's selection mode.

The plugin browser name is `AB_ReaLayer`; the GUI wordmark is **AB Rea/Layer**.
The install filename remains `VariationSampler-M11.jsfx` so existing projects
continue to find the same effect.

## Install

1. In REAPER, choose **Options → Show REAPER resource path in explorer/finder**.
2. Copy `VariationSampler-M11.jsfx` into the `Effects` folder (a subfolder is fine).
3. Refresh the FX browser and add **JS: AB_ReaLayer (0.11.1)**.
4. Drop one to four mono/stereo WAVs onto the layer cards. Multiple files fill
   consecutive slots starting from the hovered card.

Only the JSFX file is needed. No Python, scripts, fonts, images or GUI extensions
are required by the instrument. Install M11 alongside your earlier builds; existing
projects continue using their original plugin until you explicitly replace it.
M11 builds on the verified M10 engine, with a reorganised custom interface.
Output history, export and sample-rate conversion remain deferred. No companion
script is needed.

## What's new in M11

**Reset Values**, beside Randomise All, returns all four layers' volume, pan,
pitch, random pitch/gain/pan, reverse chance, attack and end release to their
factory values of zero. It preserves loaded WAVs, applied regions and drafts,
detection settings, enable/solo, selection controls, RNG progress and master
output. In ordinary mode it also preserves the limiter setting. It resets sound
values rather than restoring the patch that preceded Randomise All.

Reset Values exits Chaos through the same protected tail hold as Chaos OFF.
Existing voices retain their captured direction and envelopes; base mix changes
use the existing smoothing. New triggers use the reset values. The action
commits at an audio block boundary and requires REAPER to be processing the FX.

The opening size request is now **1550 × 1000**, 25% larger in each dimension
than the first M11 build. Controls and text scale up with the window. REAPER may
retain the size of an existing FX window; resize it once if needed. The interface
scales and letterboxes to the actual available drawing area.

The header groups master output, limiter and meters. A separate action row
places Randomise All, Reset Values and Chaos together, with Clear All Layers at
the far right. Wider layer cards keep volume, pan, pitch and reverse together.
Select a card, then use **Variations / Edit / Detect** below the cards. The right
inspector groups Random Amounts separately from Envelope. **Stop All** and
**Play Sampler** remain visible at the bottom in every workspace.

Chaos-owned values appear amber and reject edits with an explanatory hover
hint. Long filenames use ellipses; hover over a card's filename for the full
path. Audition Region/WAV labels distinguish audition from Play Sampler.

## Retained M10 features

**Randomise All** in the top-left generates sound settings for all four layers,
including empty layers. It leaves WAV assignments, regions, detection, selection
mode, enable/solo, master output and the ordinary limiter setting intact.

| Per-layer setting | Generated range |
|---|---:|
| Volume | −18 to +3 dB |
| Pan | −100% to +100% |
| Pitch | −12 to +12 semitones |
| Random pitch amount | 0–6 semitones |
| Random gain amount | 0–6 dB |
| Random pan amount | 0–100% |
| Attack | 0–200 ms, weighted toward shorter values |
| End release | 0–750 ms, weighted toward shorter values |
| Reverse chance | 0–100% |

Manual controls retain their wider ranges. Consecutive complete generated
patches cannot be identical. A dedicated generator keeps these actions separate
from MIDI region and per-voice variation selection.

**Chaos ON** sets each layer to +6 dB, base pitch randomly −24/+24 semitones,
random pan and reverse chance randomly 0/100%. Random pitch/gain/pan amounts are
maximised to 12 semitones, 12 dB and 100%. Attack/end release retain their current
values. The limiter is forced on before the louder configuration reaches DSP.

While active, Randomise All becomes **Reroll Chaos**. Controlled values are locked;
attack/end release, master output, enable/solo and other workflow controls remain
available. Base pitch plus random pitch can reach **±36 semitones**. This extreme
varispeed operation can reveal the existing linear resampler's aliasing.

**Chaos OFF** resets all four layers' volume/pan/pitch, random amounts, reverse
chance and attack/end release to zero. Master output and WAV/region assignments
remain intact. The limiter stays on while outgoing Chaos voices finish; the
button reads **Limiter: tails** during this protection, then returns to OFF.
This resets sound settings to defaults; it does not restore a pre-Chaos patch.
Save a preset first if you want to return to one later.

**Play Sampler** at the bottom-right triggers the whole instrument at velocity
100 using the same admission/variation path as a matching MIDI note. Enable,
solo, selection modes, randomisation, reverse and Chaos all apply. Click again
for another overlapping one-shot. Mouse release does not stop the sound.
Existing Audition previews the selected region; Play Sampler follows the normal
MIDI selection mode. It does not create a MIDI item or send a note downstream.

The audio engine must be processing, including when transport is stopped. GUI
actions are applied at audio block boundaries. Requests more than half a second
old are discarded, preventing delayed playback/actions after processing resumes.
Stop All/Clear cancel pending GUI actions. Host stopped-FX processing/input routing
still needs workstation acceptance; see ACCEPTANCE.md.

**Faster loading:** native-rate reading, validation, waveform peaks and detection
now share a single pass. The round-robin scheduler runs multiple bounded chunks
per GUI callback under a soft 4 ms budget. There is no resampling, no new disk
cache and no increase to the M9 memory allocation. See TEST-RESULTS.md for measured
M9/M11 loading comparisons and their limits.

M9's −4 dB master default, limiter, Clear all layers, reverse control and 96 MiB
banks are retained. Clear all requires two clicks within three seconds.

The REAPER title bar, preset controls, Param menu and bypass controls belong to
the host and remain visible. The native meter is suppressed by `no_meter`.

## Controls

Drag a knob or value field **up/down**. Hold **Shift** for fine movement.
Double-click to reset to its default. Right-click to enter a number; typing
replaces the initial value. Enter/Apply commits; Esc/Cancel dismisses. Invalid
input stays open with an explanation; out-of-range numbers are clamped.

Numeric entry uses raw parameter units: dB, semitones and milliseconds. Pan uses
-1 to +1 (random pan 0 to 1), while the display shows percentages. A random value
sets a symmetric +/- range, not a fixed offset. Numeric input depends on REAPER
routing keys to the plug-in; if keys operate REAPER instead, enable the host's
"Send all keyboard input to plug-in" option while entering values.

Attack and **end release** are captured when a voice starts. End release fades
near the sample/region's end; this is a one-shot sampler, not a note-off ADSR.
At zero, the existing edge fade remains active. Base pitch is varispeed.

## Workspaces

**Variations:** audition, region navigation, Whole WAV/Variations, selection mode,
sequence reset and a paged region grid. Clicking a waveform region selects it;
clicking a numbered tile auditions it. Excluded tiles are labelled `off`.

**Edit:** Begin region edit, then drag IN/OUT boundaries; click the waveform to
place a split cursor. Zoom, Fit and View controls navigate the draft. Split,
merge, include/exclude, Apply edits and Discard edits retain M6 behaviour.
MIDI uses applied data until Apply. Apply before auditioning the edited result.
Drafts survive tab/layer switches, but are not saved until applied.

**Detect:** threshold, hysteresis, quiet gap, minimum duration, pre-roll and tail.
After adjusting them, Reanalyse; inspect the amber preview, then Apply/Discard.
An active region-edit draft must be applied/discarded before reanalysis.

**Settings:** MIDI channel and trigger-note filters, edge fade, sequence-reset
policy/CC, selected-layer seed and fixed region, global sequence restart and Stop selected layer.
Stop All remains at the bottom. Parameter automation is available through
REAPER's Param controls even though the native sliders are hidden.

## Recall and limits

M11 retains M10/M9/M7/M6's v6 state layout and reads M4/M5 v4 state. Applied regions,
exclusions, paths, detection controls, mix settings, randomisation and envelopes
are retained. WAVs remain external. Live voices, random-sequence position,
unapplied drafts, current GUI tab and layer selection are transient.

Each layer has 16 voices and two 96 MiB decoded PCM banks. Total preallocation is
about **770.25 MiB per instance**, plus host overhead. This is a memory-resident
sampler; the limit counts decoded 64-bit samples, not the WAV file's disk size.

| WAV format | Maximum duration per layer |
|---|---:|
| 48 kHz stereo | 131.072 seconds |
| 96 kHz stereo | 65.536 seconds |
| 96 kHz mono | 131.072 seconds |
| 192 kHz stereo | 32.768 seconds |

Replacing/reanalysing/editing may need to wait for a spare bank. Loading runs in
bounded GUI chunks under a soft time budget; synchronous file reads can still stall the GUI. There is no
custom background worker. A MIDI trigger is rejected as a group if any
participating layer has no free voice. No voice stealing is added.

The limiter's fixed delay runs **even when OFF** to keep host compensation stable.
It adds approximately 2 ms to live monitoring; REAPER compensates timeline playback.
Toggling fades over 5 ms. The ceiling applies when fully enabled, not during the
transition to bypass. This is a sample-peak limiter, not a true-peak limiter or
normaliser. Light peak control is its intended use; heavy reduction can audibly
reshape transients. The meters are sampled block-peak readouts, not loudness meters.
Pitch uses linear interpolation and can alias at upward shifts. Use at least an
approximately 880 × 576 GUI; 1550 × 1000 is the intended starting size.

## Source and verification

`python3 src/build.py` rebuilds the self-contained JSFX deterministically.
The M7/M9 base uses the M6 generator/template. M10 introduced `src/m10_actions.py` and
`src/m10_loader.py`; the original GUI module names remain. `src/layout.py` defines
PCM memory, and `src/limiter.eel` supplies the protected master stage.
M11 adds `src/parameters.py` for shared sound defaults and `src/ui_layout.py`
for GUI geometry, keeping UI coordinates separate from PCM memory addresses.

See `TEST-RESULTS.md` for automated verification and `ACCEPTANCE.md` for the
remaining REAPER workstation checks. `../assets/` contains an actual offscreen
renders from the JSFX graphics engine, not design mockups.
