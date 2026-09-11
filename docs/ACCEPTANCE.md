# AB ReaLayer M11 workstation acceptance — 0.11.1

Install `AB_ReaSampler.jsfx` alongside M10. Only the main JSFX belongs in
REAPER's Effects folder. Start in a new project, then test a copy of saved work.

1. **GUI/startup:** open the plugin on your Mac, resize and move between Retina
   and non-Retina displays. Confirm the larger 1550 × 1000 opening request (host size recall may
   override it), grouped header/actions, four layer cards, workspace tabs, right
   inspector and bottom Stop All/Play Sampler. No white native slider panel.
2. **Reset Values:** randomise several times, then reset. All 36 layer sound
   values return to zero. Master output, limiter ON/OFF, WAVs, applied edits,
   unapplied drafts, enable/solo and selection settings must remain unchanged.
   Try while a long reverse/enveloped sound is playing: the active voice retains
   its direction/envelope, while a new trigger uses defaults. Reset in Chaos:
   Chaos exits, and Limiter: tails remains until outgoing protected voices end.
   Save/reopen after reset and check host automation recording of reset values.
3. **Interface:** switch all tabs and layers, open Settings, resize, drag/fine-drag
   and right-click/type controls. Inspect positive and negative pitch extremes,
   Chaos locks, long filename/full-path hover, and modal Apply/Cancel. Audition
   Region previews the selected region; Play Sampler triggers normal variation
   selection. Clear All Layers still requires its separate confirmation click.
4. **Play without a keyboard:** drop four WAVs, click Play Sampler repeatedly
   while transport is stopped and while playing. Check enable/solo, Whole WAV,
   selection modes and reverse. Release the mouse: the one-shot continues.
   Stop All stops tails. If REAPER has stopped FX processing, restore processing;
   old button presses must not unexpectedly fire. No MIDI item is created.
5. **Randomise All:** click repeatedly and check all four layers, including empty
   ones. Volume/pan/pitch, random amounts, reverse, attack and end release change;
   master output, WAVs/edits, enable/solo and selection remain intact. Short sound
   envelopes should remain useful. Save a patch and reopen it.
6. **Chaos:** enable while a tail plays. Limiter engages before the loud settings.
   Check +6 dB layer gain, ±24 base pitch, 0/100 reverse and maximum random amounts.
   Attack/release retain their current values. Controlled fields are locked.
   Reroll Chaos redraws pitch sign, pan and reverse. Listen to extremes at an
   appropriate monitor level; heavy limiting/linear varispeed are intentionally
   audible. Chaos is not a transparent normalisation mode.
7. **Chaos OFF:** sound controls reset to zero. Master, WAVs and edits remain.
   Limiter: tails remains until the previous Chaos voices finish, then OFF.
   Rapidly toggle/reroll, combine with Play and Stop All, and save/reopen while ON.
   Reopened values must not reroll. Test host automation of Chaos and sound fields;
   Chaos overrides automation of the controls it owns while enabled.
8. **Loading:** compare M10/M11 with the same one/four large 96 kHz WAVs. Check
   responsiveness while dragging controls and playing at your usual buffer size.
   Repeat with GUI hidden, cancel/replace a pending load, Clear All during load,
   and reanalyse/edit Apply/Discard. Pending jobs must not reappear after Clear.
9. **Capacity/recall:** exact-limit and oversized files should behave as in M9.
   Save four loaded layers and applied edits, reopen and compare. Test projects
   at 44.1/48/96/192 kHz and sample-rate changes within a running instance.

Automated Linux REAPER tests verify compiled graphics and numerical behavior;
native Mac input, Touch recording, listening and low-buffer scheduling still
require these workstation checks. New controls need no companion script.
