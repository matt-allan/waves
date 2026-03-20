/*
 * protocol.h — Waves link-port byte protocol
 *
 * Bidirectional serial protocol between the MCU and the Game Boy over the
 * link port.  Each message starts with a one-byte opcode followed by a
 * fixed-length payload determined by the opcode.
 *
 * All multi-byte integers are big-endian (MSB first), matching the bit
 * order of the Game Boy serial port (MSB sent first).
 */
#ifndef WAVES_PROTOCOL_H
#define WAVES_PROTOCOL_H

#include <stdint.h>

/* ---------------------------------------------------------------------- */
/* Opcodes — MCU → GB                                                      */
/* ---------------------------------------------------------------------- */

/*
 * WAVES_MSG_NOTE_ON — trigger a note on one APU channel
 *
 * Payload (3 bytes):
 *   [0] channel   — WAVES_CH_*
 *   [1] period_hi — high byte of 11-bit timer period
 *   [2] period_lo — low byte of 11-bit timer period
 *
 * The MCU pre-computes the period from the MIDI note number so the GB
 * does not need a note-to-period lookup table.
 */
#define WAVES_MSG_NOTE_ON     0x01

/*
 * WAVES_MSG_NOTE_OFF — release a note on one APU channel
 *
 * Payload (1 byte):
 *   [0] channel — WAVES_CH_*
 */
#define WAVES_MSG_NOTE_OFF    0x02

/*
 * WAVES_MSG_PATCH_LOAD — load a complete patch onto one APU channel
 *
 * Payload (2 + WAVES_PATCH_SIZE bytes):
 *   [0]     channel — WAVES_CH_*
 *   [1]     reserved (0x00)
 *   [2..N]  patch bytes (see WAVES_PATCH_SIZE)
 *
 * Sent by the MCU at boot to restore the last-saved patch state.
 */
#define WAVES_MSG_PATCH_LOAD  0x03

/*
 * WAVES_MSG_CC_UPDATE — update a single patch parameter (from MIDI CC)
 *
 * Payload (3 bytes):
 *   [0] channel — WAVES_CH_*
 *   [1] param   — WAVES_PARAM_*
 *   [2] value   — 0–127 (MIDI CC range)
 */
#define WAVES_MSG_CC_UPDATE   0x04

/* ---------------------------------------------------------------------- */
/* Opcodes — GB → MCU                                                      */
/* ---------------------------------------------------------------------- */

/*
 * WAVES_MSG_PATCH_SAVE — user requested a patch save from the GB editor
 *
 * Payload (2 + WAVES_PATCH_SIZE bytes):
 *   [0]     channel — WAVES_CH_*
 *   [1]     reserved (0x00)
 *   [2..N]  patch bytes
 *
 * The MCU should persist these bytes.  No acknowledgement is sent; if
 * the link drops the GB continues making sound with the local patch.
 */
#define WAVES_MSG_PATCH_SAVE  0x10

/* ---------------------------------------------------------------------- */
/* Channel IDs                                                              */
/* ---------------------------------------------------------------------- */

#define WAVES_CH_PU1   0    /* Pulse channel 1 (with sweep) */
#define WAVES_CH_PU2   1    /* Pulse channel 2              */
#define WAVES_CH_WAV   2    /* Arbitrary waveform channel   */
#define WAVES_CH_NOISE 3    /* LFSR noise channel           */

/* ---------------------------------------------------------------------- */
/* Patch parameter IDs (for WAVES_MSG_CC_UPDATE)                           */
/* ---------------------------------------------------------------------- */

/* Common to PU1, PU2, NOISE */
#define WAVES_PARAM_ATTACK    0x00
#define WAVES_PARAM_DECAY     0x01
#define WAVES_PARAM_SUSTAIN   0x02
#define WAVES_PARAM_RELEASE   0x03

/* PU1 / PU2 */
#define WAVES_PARAM_DUTY      0x10  /* 0–3 maps to 12.5 / 25 / 50 / 75 % */

/* PU1 sweep */
#define WAVES_PARAM_SWEEP_PACE  0x20
#define WAVES_PARAM_SWEEP_DIR   0x21  /* 0 = up, 1 = down */
#define WAVES_PARAM_SWEEP_STEP  0x22

/* WAV */
#define WAVES_PARAM_WAV_VOLUME  0x30  /* 0–3 */

/* ---------------------------------------------------------------------- */
/* Patch sizes (bytes transmitted in PATCH_LOAD / PATCH_SAVE payload)      */
/* ---------------------------------------------------------------------- */

#define WAVES_PATCH_SIZE_PU1    8   /* duty, A, D, S, R, sweep_pace, dir, step */
#define WAVES_PATCH_SIZE_PU2    5   /* duty, A, D, S, R */
#define WAVES_PATCH_SIZE_WAV   21   /* volume, A, D, S, R, 16 wave bytes */
#define WAVES_PATCH_SIZE_NOISE  5   /* clock_div, shift_width, A, D, S, R — TODO */

/* Maximum patch payload size (for buffer sizing) */
#define WAVES_PATCH_SIZE_MAX    WAVES_PATCH_SIZE_WAV

/* Total message length including opcode, for each opcode */
#define WAVES_MSG_LEN_NOTE_ON     4  /* opcode + channel + period_hi + period_lo */
#define WAVES_MSG_LEN_NOTE_OFF    2  /* opcode + channel */
#define WAVES_MSG_LEN_CC_UPDATE   4  /* opcode + channel + param + value */

#endif /* WAVES_PROTOCOL_H */
