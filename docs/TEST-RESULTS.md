# AB ReaLayer branding update — 0.11.1

The user-edited JSFX is now reflected in the source generator: FX browser name
`AB_ReaLayer (0.11.1)`, GUI title `AB Rea/Layer`, subtitle
`Multilayer Random Variation Sampler for REAPER     V0.11.1`, and **Reset Values**.
The locked-control hover message also uses Reset Values. Version, filename,
parameter IDs, opening dimensions and audio code are retained.

Generated output was compared byte-for-byte against the supplied JSFX: it is
identical except for the matching Reset Values hover wording. **18 targeted
checks passed** (2 startup, 16 GUI). The branded 1550 × 1000 capture was visually
inspected. No audio changes were introduced; previous engine reports below
remain historical verification of their recorded source hashes.

Source SHA-256: `22832bcdae2d4b7b7a032ec4d01f783dec5c5358128eecc0b13541a22a4681dd`
Reports: tests/results/branding-startup-results.json and branding-gui-results.json.
Current GUI capture: previews/AB-ReaLayer.png. Earlier captures remain historical.

---

# M11 window-size update — 0.11.1

Opening size increased from 1240 × 800 to 1550 × 1000. The logical canvas
remains 1240 × 800, so controls and text render 25% larger at the new size.

**18 targeted checks passed:** startup heartbeat/negative control (2) and
compiled GUI contract, drawing and interaction scenarios (16). The 1550 × 1000
capture was visually reviewed; see previews/window-large.png. Production bytes
were compared against 0.11.0: only version labels and the @gfx opening dimensions
changed. Audio/DSP and GUI logic are byte-identical, so the full audio/loading
suite was not repeated for this sizing patch. Native OS window-size recall still
needs workstation confirmation.

Updated source SHA-256: `b777f3f7618dfa291f7d28cbd1559588354282237d4d88351e398bab0823ca3b`
New reports: tests/results/size-startup-results.json and size-gui-results.json.
Original reports and captures below document the preceding 0.11.0 full release.

---

# M11 verification — 0.11.0

**205 automated checks passed** through the complete release runner on
REAPER 7.79 Linux x86_64. GUI startup and execution are required gates. The
production JSFX rebuilds byte-for-byte from the included generator sources.
The verified M10 release remains unchanged.

Source SHA-256: `4a42f8e96529f9b24f48295025b8f25d14c668a71bd14b678b6c9fb0e34f8ac0`

| Suite | Passed |
|---|---:|
| startup | 2 |
| gui | 16 |
| feature | 32 |
| macro | 23 |
| capacity | 4 |
| layer | 26 |
| lifecycle | 28 |
| hardening | 18 |
| edit | 54 |
| loading | 2 |

## M11 coverage

Six additional audio/state checks cover reset with the ordinary limiter OFF
and ON; preservation of master, WAVs, edited regions, exclusions, enable/solo,
selection and advanced macro RNG state; next-trigger audio matching the default
patch exactly; repeated reset without RNG rewind; saved reset-state recall;
and exiting Chaos while its active tails retain limiter protection.

The GUI suite executes the complete compiled drawing/input code, then reads
saved telemetry and host parameters. It covers Variations, Edit, Detect,
Settings, numeric entry, drag/fine drag/double-click, invalid input and clamping,
editor split/merge/exclusion/Apply, limiter/reverse/Clear, global macros, Chaos,
Reset Sound and filename hover. Captures use 1240 × 800, 1100 × 720, 880 × 576 and
1860 × 1200 surfaces. They were visually inspected, including amber Chaos values,
positive/negative pitch readability and the numeric modal. The parameter-ID and
GUI/audio variable ownership guards pass. No production test slider is included.

The startup suite includes the full @gfx heartbeat and an intentionally broken
scientific-literal negative control, guarding against the earlier M8 failure.

## Retained engine regression

Play Sampler matches a corresponding velocity-100 MIDI note. Coverage includes
solo/mute, filters, queue limits/staleness, panic/clear and voice exhaustion;
100 generated patches, saved patches and Chaos activation/recall/locking/tails;
reverse probability/direction, pitch and envelopes; exact-limit 96 MiB mono and
stereo banks and one-frame-over rejection; four-layer admission, bank lifecycle,
region editing, exclusions, publication and recall.

Limiter fixtures cover quiet input, overloads, bypass and toggling at
44.1/48/96/192 kHz. Fully enabled output meets the −0.1 dBFS sample-peak ceiling
for those fixtures. Numerical testing does not establish perceptual transparency.

## Retained loading benchmark

The M11 loader retains the M10 fused native-rate implementation. The release
runner compares it against the included immutable M9 fixture using 96 kHz stereo
WAVs. Timing starts at load initiation and ends at READY publication; startup,
memory allocation and fixture creation are excluded.

| Fixture | M9 baseline | M11 | Speedup over M9 |
|---|---:|---:|---:|
| 60 s WAV, 1 layer(s) | 44.03 s | 2.55 s | 17.3× |
| 60 s WAV, 4 layer(s) | 177.93 s | 9.48 s | 18.8× |

Region pairs, cached waveform peaks and 2,048 sampled interleaved PCM positions
per bank match the baseline exactly. This is not a full-file PCM hash or a claim
of further speedup over M10. The test's internal M10 scenario labels identify the
retained loader generation; its updated source hash is the M11 hash above.
Local Linux scratch-storage timing does not predict cold/network-disk or Mac
performance. The 4 ms GUI work budget is soft; synchronous reads can exceed it.
Project-open restoration remains synchronous.

## Reproduce and workstation acceptance

Use Python 3, NumPy, SciPy, Pillow and an installed REAPER executable:

```sh
python3 src/build.py
python3 tests/run_release.py --reaper /absolute/path/to/reaper --output /tmp/m11-release
```

Use a fresh output directory. The old M9 four-layer loading fixture deliberately
takes several minutes. Install only the root M11 JSFX; source/test files are
optional development materials. Machine-readable reports are in tests/results/.

Native macOS/Windows input, drag/drop, Retina/display changes, actual host window
size recall, Touch automation recording, transport-stopped processing policy,
listening and worst-case low-buffer scheduling remain workstation checks in
ACCEPTANCE.md. Offscreen synthetic events do not test OS event delivery.
