# TODO

## Bug fixes

- [x] `waves.c` `pu2_set_duty_cycle`: reads `NR11_REG` instead of `NR21_REG`
      (copy-paste bug, wrong channel register)
- [x] `envelope.c` `envelope_next`: missing return after switch statement —
      undefined behavior if `stage` has an unexpected value
- [x] `envelope.c` `envelope_decay`: `target_volume = volume - sustain` treats
      sustain as a delta; decide whether sustain is a level (0–15) or a delta
      and make it consistent throughout

## Engine

- [ ] Noise channel — implement `struct noise`, `noise_trigger`, `noise_update_env`
      using NR41–NR44 registers
- [ ] Wire PU2 and WAV back into the timer ISR and main loop (currently commented out)

## Serial protocol

- [ ] Define message format (framing, opcodes, payload layout)
- [ ] MCU → GB
- [ ] GB -> MCU

## UI / screen

- [ ] Main screen — list 4 instruments + mixer, navigate with d-pad
- [ ] Instrument editor — per-parameter knob navigation, values match CC params
- [ ] Mixer screen — per-instrument volume/pan, master volume
- [ ] MIDI channel assignment — per-instrument, shown in instrument editor
- [ ] Graphics / tiles
