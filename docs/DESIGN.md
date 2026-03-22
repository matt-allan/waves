# Waves — Design Overview

An alternative Game Boy MIDI sound module, similar to mGB but with full ADSR
envelopes, more polyphony control, and a synth-style interface.

## Goals

- Expose the full Game Boy APU as a MIDI sound module driven over the link port
- Keep the GB doing only what requires tight timing; offload everything else to
  the MCU
- Allow sounds to be tweaked live via joypad (like knobs on a synth) or MIDI CC
- Run on cheapest available flash carts (no save RAM)

## Hardware

**Game Boy APU — 4 channels:**

| Channel | Type | Hardware envelope | Notes |
|---------|------|-------------------|-------|
| PU1 | Pulse (square) | Yes | Supports frequency sweep |
| PU2 | Pulse (square) | Yes | No sweep |
| WAV | Arbitrary waveform | No (2-bit volume only) | 4-bit samples, 32 nibbles |
| NOISE | LFSR noise | Yes | Programmable frequency/width |

**Link port serial** connects to an MCU (e.g. Arduino) that handles MIDI.

## Architecture

```
MCU (source of truth)          GB (audio + UI)
├── MIDI parsing                ├── APU hardware
├── Note routing                ├── Software ADSR envelopes (timer ISR)
├── Patch storage               ├── Knob UI (joypad)
├── Preset management           └── Screen
└── MIDI channel assignments
          ↕ link port serial
     note-on/off + period
     CC / param updates
     patch sync (on boot)
     param change notify (knob edits)
```

### Why the MCU owns storage

The GB has no persistent storage without an expensive flash cart. The MCU holds
the canonical patch state and MIDI channel assignments. On boot the MCU sends
the current state to the GB before sound starts.

### Why ADSR lives on the GB

The GB APU's hardware envelope is limited (one direction, fixed pace). Full ADSR
requires a software timer loop running at 64 Hz to match the DIV-APU sweep rate.
Anything with tight timing requirements stays on the GB; everything else is
offloaded.

## Instruments

The GB exposes 4 instruments, one per APU channel. Each instrument has:

- A patch (channel-specific parameters, see below)
- A MIDI channel assignment (which MIDI channel triggers this instrument)

Multiple instruments can share a MIDI channel for polyphony (e.g. PU1 + PU2
both on MIDI channel 1 gives two-voice polyphony).

### Patch parameters

**PU1 / PU2:**
- Duty cycle (12.5%, 25%, 50%, 75%)
- ADSR (attack, decay, sustain, release)
- Frequency sweep (PU1 only): pace, direction, step

**WAV:**
- Wave pattern (16 bytes, 32 4-bit samples)
- Volume (0–3)
- ADSR (software envelope mapping to the 2-bit hardware volume)

**NOISE:**
- Clock divider and shift register width
- ADSR

## Serial Protocol

Bidirectional over the Game Boy link port at 31,250 baud (external clock,
driven by the MCU — the same rate as MIDI). See `src/midilink/protocol.h`
for the full message format and command definitions.

## UI

Main screen lists the 4 instruments and a mixer entry. Selecting an instrument
opens its patch editor.

**Patch editor:**
- D-pad navigates and increments/decrements parameters (knob-style)
- Parameters match what MIDI CC can also control
- Select triggers a preview note at middle C on the current instrument

**Mixer:**
- Per-instrument volume and pan
- Master volume