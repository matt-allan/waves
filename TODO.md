# TODO

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
