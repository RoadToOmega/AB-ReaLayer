# AB ReaLayer — Milestone 11 architecture — 0.11.1

M11 builds on verified M10 v0.10.0's four-layer engine and custom vector GUI. M8 history buffers,
export code and companion scripts are absent. `src/build.py` produces one
self-contained JSFX. Original M7 sources are retained separately.

## Source boundaries

- `layer-template.jsfx`, `m6_transform.py`, `edit-engine.eel`: retained loader,
  detector, bank lifecycle, voice processing and region editor.
- `build.py`: layer namespaces, MIDI admission, direction/clear extensions,
  host parameters and master stage assembly.
- `m10_actions.py`: global sound actions, a private macro RNG, bounded command
  transport, Chaos state/protection, cached sound parameters and voice tags.
- `m10_loader.py`: fused native-rate validation, peak and detection pass.
- `layout.py`: shared bank capacity, layer stride and master memory addresses.
- `limiter.eel`: audio-owned lookahead, stereo gain and delay compensation.
- `m7_gui.py`, `gui-controls.eel`, `gui-layer.eel`, `gui-frame.eel`: parameter
  registry, drawing, gestures, cards, workspaces and new header actions.
- `eel_syntax.py`: build-time literal guard against the previous @gfx failure.

## M11 presentation and reset boundaries

- `parameters.py`: shared PARAMS registry and the 36 SOUND_DEFAULTS. Widget
  double-click reset, Reset Values and Chaos OFF derive from this same registry.
- `ui_layout.py`: 1550 × 1000 opening request, 1240 × 800 logical size, shared rectangles, card geometry and
  central workspace translation. `layout.py` continues to own PCM memory only.
- `m10_actions.py`: adds opcode 4 and `master_reset_sound()`; no new host parameter,
  serialization field, PCM bank or voice allocation is needed.

Reset Values publishes only an opcode/timestamp through the existing SPSC ring.
At `@block`, normal mode fills the private patch with defaults and commits its
36 values through the existing direct automation dispatch. It neither draws new
random numbers nor touches selection/reset mailboxes. In Chaos it invokes
`master_chaos_off()`, which uses the same reset helper and protects outgoing
Chaos tails before bypassing the limiter. The sound snapshot is refreshed before
voice admission. WAV banks, draft edits and loader state are outside this action.

Header/actions/cards/tabs/inspector/footer use absolute logical coordinates.
The central Variations/Edit/Detect workspace has a GUI-only +70 vertical
translation, applied equally to rectangles, lines, text, knobs, hit tests and
menu placement. Drawing and pointer input use one proportional scale and
centering offset derived from actual `gfx_w/gfx_h`. Resizing cancels active
control gestures. REAPER owns actual window placement and may retain old sizes.

The GUI generator preserves global `master_` identifiers and `#master_` strings
inside each namespaced layer. Shared geometry expands before namespacing. Layer
local slider references continue to map from template IDs; explicit global
reads inside a layer use `slider(id)`. Filename ellipsis and tooltip wrapping use
`gfx_measurestr` and run only on the GUI thread. No image assets are required.

## Real-time ownership and banks

`@gfx` pumps round-robin chunks of file loading, detection and edit work under
a soft 4 ms budget, with a hard maximum of 16 chunks per callback. JSFX has no
custom worker; disk I/O can block the GUI. `@block` handles MIDI, control mailboxes, global sound actions, committed
parameter snapshots, bank adoption and limiter configuration. `@sample` advances voices, sums layers,
applies master gain, processes the limiter and updates meters. The audio path
performs no disk I/O, allocation, locks or waits.

Each layer has two immutable published PCM banks. GUI writes only a private
WRITING bank, finishes metadata and then publishes READY. Audio adopts at a block
boundary. Generation tokens reject stale jobs; voice references and reader pins
keep retired banks alive until safe reuse. All-or-none admission keeps four-layer
MIDI triggers together. Sixteen voices are available per layer.

| Memory item | Double slots |
|---|---:|
| Control/metadata per layer | 65,536 |
| Each PCM bank | 12,582,912 |
| Layer stride | 25,231,360 |
| Four-layer end / limiter base | 100,925,440 |
| Master reservation | 32,768 |
| Total maxmem/preallocation | 100,958,208 |

A bank is 96 MiB of decoded doubles. Total is 770.25 MiB plus host overhead.
Capacity checks use actual memory availability and frames × channels. All GUI
and DSP offsets derive from the same layout constants. Test graphics capture
uses an otherwise unused spare bank only in fixtures; it is absent in production.

## Reverse voices

Each layer has independent seeded MIDI and audition direction RNGs, separate from
its existing selection and pitch/gain/pan RNGs. Sequence reset reseeds them.
After admission, reverse chance selects a Boolean stored in previously unused
voice slot 23. Slider edits cannot change an existing voice's direction.

The logical playback cursor still advances forward. For reverse voices, the
source read position is `end - 1 - (cursor - start)`, clamped to the captured
region. Stereo channels share the coordinate; original linear interpolation and
pitch step apply. Traversal-based attack, end release and completion remain
unchanged. No PCM reversal or copying occurs. Whole WAV and manual audition use
the same direction-capable voice reader.

## Clear-all transaction

The first GUI click arms a three-second confirmation. The second discards drafts,
cancels each loader and advances each request generation before publishing the
atomic global-clear mailbox. At the next audio block, all four layers detach
their assignments and release voices with the existing emergency fade. Ready
banks cannot be adopted during that clear block, and stale generation results
are retired. Reference counts determine when old PCM becomes reusable.

Serialization sees a pending clear as empty assignments. Mix, envelope, selection
and reverse parameters remain intact. The action does not delete source files.

## Master limiter

The master gain precedes the limiter. A fixed stereo ring delays output by
`round(srate × 0.002)` frames (bounded to 1…4094). A monotonic deque tracks the
largest linked stereo input peak over the lookahead window. It uses bounded
storage and amortized O(1) work per sample; a single update can remove multiple
entries, so worst-case host scheduling still needs workstation measurement.

Required gain is min(1, ceiling/window peak), with a −0.1 dBFS ceiling. Linear
attack can traverse the gain range within the delay; release varies from 50 to
150 ms with reduction. A final gain bound handles output rounding. Test telemetry
verifies the guard did not need to rescue the attack in the tested overloads.

A five-millisecond wet-gain transition switches limiting without changing the
delay. Both ON and OFF therefore report constant PDC. Rate changes reset queue
and delay memory. Audio publishes a gain-reduction scalar atomically for GUI
reading. This is a sample-peak design; intersample peaks are not measured.

## GUI, parameters and state

The 1240 × 800 logical vector canvas scales with a shared coordinate transform;
macOS Retina is requested. No raster skins, fonts or GUI extensions are needed.
Native parameters remain the source of truth; all default slider rows are hidden.

| Parameter | Meaning |
|---|---|
| 1 | Master output, new default −4 dB |
| 2–62 | Existing M7 identities, ranges and defaults |
| 63 | Reserved, hidden |
| 64 | Master limiter, OFF by default |
| 65–68 | Layers 1–4 reverse chance, 0–100%, default 0 |
| 69 | Chaos mode, default OFF |
| 70 | Hidden macro RNG state, 24-bit integer |

GUI automation dispatch uses direct `slider_automate(sliderN, finish)` calls,
including parameters above 64, instead of overflowing a bitmask. Global actions
use generated direct notifications from their audio-block commit path. Gestures finish
on release/cancel; numeric entry validates and clamps input. GUI-owned state
and audio-owned accumulators remain separate. Actions use atomic mailboxes;
waveform views use bounded generation-verified reader pins.

The outer state remains v6 (magic 73104), with inner v4 bank tables and inclusion
flags. v4 outer legacy states remain readable. Applied regions and settings are
saved; source WAVs remain external. Drafts, PCM, live voices and RNG progression
are transient. Host parameters store limiter/reverse, Chaos and macro RNG state values. Saved master output
is respected; only fresh/default-reset values change to −4 dB. Installing M11 does
not migrate existing FX instances automatically.

## M10 action and trigger pipeline

The GUI producer writes opcode/timestamp into a 16-entry ring, then atomically
publishes the write counter. The audio consumer reads only published slots and
acknowledges after copying each command. It processes at most 16 commands per
block. Full queues reject new requests; they do not overwrite unread payloads.
Requests older than 0.5 seconds, or pending during Panic/Clear, are discarded.
These transient requests are not serialized or recorded as MIDI events.

Randomise generates 36 sound values into a private patch. Generated values use
parameter steps; a complete-patch comparison forces a small in-range change in
the unlikely case of a consecutive duplicate. The independent LCG state stays
in the 24-bit integer range so host float serialization retains it exactly.
Region selection and per-voice modulation RNGs remain untouched by macros.

Macros commit all values within `@block`. Voice start and mix setup read an
audio-owned sound snapshot instead of concurrently changing GUI sound sliders.
Normal control automation refreshes that snapshot at block boundaries. Existing
sample-wise gain/pan/pitch smoothing and per-voice direction/envelope latching
remain. Direct host automation of Chaos-owned settings is overridden while the
mode is active; GUI widgets prevent editing them. Attack/release remain editable.

Play requests become velocity-100 note events at offset zero in the existing
internal queue, before received events. They represent a note matching the
configured channel/note filter, so no extra filtering can silence the Play
button. External MIDI keeps its existing filters. Both event sources share the
same participating-layer evaluation, all-or-none admission and `start_voice(...,0)`
path. No `midisend()` loopback is used. Queue overflow and voice exhaustion are
bounded and retain existing rejection behavior.

The order is: clear latch → actions → limiter configuration → sound snapshot →
layer/bank state → Play/MIDI queue → sample-offset dispatch → voices → master
smoothing → limiter. Actions queued in one callback retain their order. Multiple
Play requests consumed in one audio block start together at its first sample.

## Chaos state and limiter protection

Phase 0 is ordinary operation. Turning Chaos on writes/display-notifies the new
patch and enters phase 1, enabling the limiter. The DSP sound snapshot remains
at its previous values until limiter wet reaches 1; then phase 2 activates the
new patch. Rerolling while already active uses the same protected pipeline.
Fresh saved Chaos presets load their committed values without rerolling. Invalid
extreme fields in a mode-ON preset are normalised to the required Chaos ranges.

Turning Chaos off resets the 36 sound settings and enters phase 3. Each voice
has an auxiliary master-memory tag recording whether it began under Chaos; this
does not change the existing 24-slot voice stride. Tagged active voices keep
limiting engaged. Once they finish, a short clearance interval covers the delayed
output; the original smooth limiter bypass transition then runs. New ordinary
voices do not indefinitely extend this hold. Sample-rate changes retain the
existing delay reconfiguration behavior.

Patch/snapshot/command/tag memory uses the previously unused part of M9's 32,768
master slots. PCM banks, four-layer strides and total preallocation are unchanged.

## Fused native-rate loading

Each `file_mem()` call reads at most 16,384 interleaved items. The subsequent loop
visits each mono/stereo frame once, validates both channels, updates the existing
256 min/max peak pairs, and feeds the original RMS-window detector. Window energy,
quiet gap and region-padding state cross chunk boundaries unchanged. Final window
and open-region flushes run only at EOF, before publication.

PCM-only restore/edit loads skip detection and retain supplied region tables.
The standalone analysis path is retained for existing jobs that explicitly enter
analysis state. Invalid PCM, short reads and cancellation never publish a bank.
Source rate, frame coordinates, region inclusion flags and immutable-bank reader
pins remain unchanged. No file resampling, source rewriting or background thread
is introduced.

`master_pump_one()` preserves the work-conserving round-robin primitive.
`master_pump_loaders()` repeats it until no jobs remain, 16 chunks have run, or
4 ms have elapsed. The budget is checked between chunks; synchronous file I/O or
one expensive chunk can exceed it. This is not a hard realtime GUI deadline.
Project restoration in `@serialize` still runs synchronously under the existing
bounded bank-capacity loop and is not paced by GUI callbacks. The measured large
speedup describes interactive loading, not an equivalent promise for project open.

## Verification limits

The release gate requires real REAPER audio/state, compiled @gfx execution and a
startup negative control. Synthetic GUI events exercise plugin logic, not native
OS routing. Tests establish numerical correctness for the fixtures, not arbitrary
race freedom, perceptual transparency or a worst-case low-buffer CPU deadline.
Native macOS/Windows, host Touch recording and listening checks remain acceptance
work. Linear resampling, external-file identity and fixed bank sizes are retained
limitations of the M7 base.
