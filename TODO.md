# TODO

## Bug fixes

- [ ] `waves.c` `pu2_set_duty_cycle`: reads `NR11_REG` instead of `NR21_REG`
      (copy-paste bug, wrong channel register)
- [ ] `envelope.c` `envelope_next`: missing return after switch statement —
      undefined behavior if `stage` has an unexpected value
- [ ] `envelope.c` `envelope_decay`: `target_volume = volume - sustain` treats
      sustain as a delta; decide whether sustain is a level (0–15) or a delta
      and make it consistent throughout

## Engine

- [ ] Noise channel — implement `struct noise`, `noise_trigger`, `noise_update_env`
      using NR41–NR44 registers
- [ ] Wire PU2 and WAV back into the timer ISR and main loop (currently commented out)
- [ ] Remove frequency table from `waves.h` — GB receives periods from MCU directly;
      replace with `MIDDLE_C_PERIOD 1046` constant for preview mode

## Preview / standalone mode

- [ ] Refactor hardcoded test values out of `main()` into a proper preview path
- [ ] Select held → note-on at `MIDDLE_C_PERIOD` on current instrument;
      Select released → note-off
- [ ] Stub for MCU detection — if no MCU connected on boot, enter standalone mode

## Serial protocol

- [ ] Define message format (framing, opcodes, payload layout)
- [ ] MCU → GB: patch load, note-on (channel + period), note-off, CC param update
- [ ] GB → MCU: patch save (user-initiated, sends full patch), MIDI assignment changed
- [ ] Link port serial ISR — receive bytes, dispatch to engine functions
- [ ] Startup handshake — wait for MCU patch state before enabling sound;
      fall back to standalone mode after timeout

## UI / screen

- [ ] Main screen — list 4 instruments + mixer, navigate with d-pad
- [ ] Instrument editor — per-parameter knob navigation, values match CC params
- [ ] Mixer screen — per-instrument volume/pan, master volume
- [ ] MIDI channel assignment — per-instrument, shown in instrument editor
- [ ] Graphics / tiles
