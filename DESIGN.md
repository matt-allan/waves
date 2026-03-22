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
driven by the MCU — the same rate as MIDI).

### Header byte

Every message starts with one header byte:

```
  7   6   5   4   3   2   1   0
[ II  II  CCC CCC DDD DDD DDD ]
```

- **II** (bits 7–6) — instrument: 0=PU1, 1=PU2, 2=WAV, 3=NOISE
- **CCC** (bits 5–3) — command (see table below)
- **DDD** (bits 2–0) — inline data; only used by NOTE_ON (carries `period[10:8]`),
  zero for all other commands

Decoding in the ISR is three cheap bit operations with no memory access:

```c
enum instrument instr = hdr >> 6;
enum cmd        cmd   = (hdr >> 3) & 7;
uint8_t         data  = hdr & 7;
```

### Commands

| CCC | Name | Dir | Extra bytes | Notes |
|-----|------|-----|-------------|-------|
| 0 | NOTE_ON | MCU→GB | period[7:0] | DDD = period[10:8]; NOISE: DDD=0, byte = NR43 |
| 1 | NOTE_OFF | MCU→GB | — | |
| 2 | SET_PARAM | both | param_id, value | covers boot patches, CC, and MIDI channel assignment |

3–7 reserved.  No handshake — like MIDI, the sender streams bytes and the
receiver processes them.  No connection setup, no ACK, no fallback mode.

NOTE_ON is two bytes total; NOTE_OFF is one byte; SET_PARAM is three bytes.
The MCU pre-computes the 11-bit APU period (or NR43 for NOISE) from the MIDI
note number — the GB never touches a lookup table.

### Patch parameters (SET_PARAM payload)

| param_id | Name | Range | Applies to |
|----------|------|-------|-----------|
| 0 | ATTACK | 1–7 | all |
| 1 | DECAY | 1–7 | all |
| 2 | SUSTAIN | 0–15 | all (absolute volume level) |
| 3 | RELEASE | 1–7 | all |
| 4 | DUTY_CYCLE | 0–3 | PU1, PU2 |
| 5 | SWEEP_PACE | 0–7 | PU1 (0 = off) |
| 6 | SWEEP_DIR | 0–1 | PU1 |
| 7 | SWEEP_STEP | 0–7 | PU1 |
| 8 | VOLUME | 0–3 WAV, 0–15 NOISE | WAV, NOISE |
| 9–24 | WAVE_0–WAVE_15 | 0–255 | WAV wave RAM bytes |
| 25 | NOISE_DIV | 0–7 | NOISE (NR43 bits 2:0) |
| 26 | NOISE_WIDTH | 0–1 | NOISE (NR43 bit 3: 0=15-bit LFSR, 1=7-bit) |
| 27 | CHAN_VOLUME | 0–7 | mixer per-instrument |
| 28 | CHAN_PAN | 0–2 | mixer (0=L, 1=both, 2=R) |
| 29 | MIDI_CHANNEL | 0–15 | MIDI channel assignment |

MIDI_CHANNEL is sent MCU→GB on boot (so the UI can display the assignment)
and GB→MCU immediately when the user changes it (so the MCU can update routing).

### Boot sequence

```
MCU                              GB
 |--- SET_PARAM × N ------------>|  full patch state for all 4 instruments
 |         [NOTE_ON when ready]   |  GB applies params as they arrive
```

No handshake.  Like MIDI, the MCU streams bytes when it is ready and the GB
processes them.  The GB sits idle until the first message arrives; there is
no standalone mode because the MCU is the only source of notes.

### Runtime — MCU → GB

The MCU performs all MIDI parsing and voice allocation. When a MIDI note-on
arrives it selects an instrument, computes the APU period, and sends NOTE_ON.
CC messages map to param_id values and arrive as SET_PARAM.

### Runtime — GB → MCU

**Patch edits are local until saved.** Parameter changes made via the joypad
editor are applied immediately (zero-latency). When the user explicitly saves,
the GB sends one SET_PARAM per parameter for the full patch. The MCU stores it
persistently. No ACK; if the link drops the GB keeps making sound.

MIDI channel assignments changed in the UI are sent immediately as MIDI_ASSIGN
so the MCU can update its routing table without waiting for a save.

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