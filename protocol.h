/*
 * protocol.h — wire protocol for the Game Boy ↔ MCU link port serial connection.
 *
 * Every message starts with a header byte:
 *
 *   7   6   5   4   3   2   1   0
 *  [V   II  II  CC  CC  CC  CC  CC]
 *
 *  V  (bit 7)    — 0 = instrument-specific, 1 = global (TBD)
 *  II (bits 6:5) — instrument (when V=0): 0=PU1, 1=PU2, 2=WAV, 3=NOISE
 *  CC (bits 4:0) — command
 *
 * Commands 0–4 are common to every instrument (same meaning, same ID).
 * Commands 5+ are instrument-specific.
 *
 * Payload following the header:
 *   - Most commands: one value byte.
 *   - PATCH_SAVE, PATCH_LOAD: one patch number byte.
 *   - WAV_SET_WAVE: 16 wave RAM bytes.
 *
 * Direction:
 *   GB  → MCU: instrument commands (params, patch save/load)
 *   MCU → GB:  instrument commands (param updates, patch load responses)
 *              + note events (reserved high command slots, TBD)
 *
 * This file is plain C99 and is shared by the GB ROM (SDCC) and the MCU side.
 */
#ifndef WAVES_PROTOCOL_H
#define WAVES_PROTOCOL_H

#include <stdint.h>

/* ---------------------------------------------------------------------- */
/* Instruments                                                              */
/* ---------------------------------------------------------------------- */

enum instrument {
	INSTR_PU1   = 0,
	INSTR_PU2   = 1,
	INSTR_WAV   = 2,
	INSTR_NOISE = 3,
};

/* ---------------------------------------------------------------------- */
/* Common instrument commands (IDs 0–4, identical across all instruments)  */
/* ---------------------------------------------------------------------- */

enum common_cmd {
	CMD_CHAN_VOLUME  = 0, /* mixer output volume 0–7                    */
	CMD_CHAN_PAN     = 1, /* pan: 0=left, 1=both, 2=right               */
	CMD_MIDI_CHANNEL = 2, /* MIDI channel assignment 0–15               */
	CMD_PATCH_SAVE   = 3, /* save current params as patch N             */
	CMD_PATCH_LOAD   = 4, /* load patch N and stream all params to GB   */
	/* 5–27: instrument-specific (see per-instrument enums)             */
	CMD_NOTE_OFF     = 28, /* MCU → GB only; no payload                 */
	CMD_NOTE_ON      = 29, /* MCU → GB only; 2 bytes: period[10:8], period[7:0] */
	/* 30–31 reserved */
};

/* ---------------------------------------------------------------------- */
/* PU1 commands                                                            */
/* ---------------------------------------------------------------------- */

enum pu1_cmd {
	PU1_CHAN_VOLUME  = 0,
	PU1_CHAN_PAN     = 1,
	PU1_MIDI_CHANNEL = 2,
	PU1_PATCH_SAVE   = 3,
	PU1_PATCH_LOAD   = 4,
	PU1_ATTACK       = 5,  /* envelope attack pace 1–7                  */
	PU1_DECAY        = 6,  /* envelope decay pace 1–7                   */
	PU1_SUSTAIN      = 7,  /* sustain volume level 0–15                 */
	PU1_RELEASE      = 8,  /* envelope release pace 1–7                 */
	PU1_DUTY_CYCLE   = 9,  /* duty cycle 0–3 (12.5 / 25 / 50 / 75 %)   */
	PU1_SWEEP_PACE   = 10, /* frequency sweep pace 0–7 (0 = off)        */
	PU1_SWEEP_DIR    = 11, /* sweep direction: 0 = up, 1 = down         */
	PU1_SWEEP_STEP   = 12, /* sweep step magnitude 0–7                  */
	/* 13–31 reserved (note events, MCU → GB only, TBD) */
};

/* ---------------------------------------------------------------------- */
/* PU2 commands                                                            */
/* ---------------------------------------------------------------------- */

enum pu2_cmd {
	PU2_CHAN_VOLUME  = 0,
	PU2_CHAN_PAN     = 1,
	PU2_MIDI_CHANNEL = 2,
	PU2_PATCH_SAVE   = 3,
	PU2_PATCH_LOAD   = 4,
	PU2_ATTACK       = 5,
	PU2_DECAY        = 6,
	PU2_SUSTAIN      = 7,
	PU2_RELEASE      = 8,
	PU2_DUTY_CYCLE   = 9,
	/* 10–31 reserved */
};

/* ---------------------------------------------------------------------- */
/* WAV commands                                                            */
/* ---------------------------------------------------------------------- */

enum wav_cmd {
	WAV_CHAN_VOLUME  = 0,
	WAV_CHAN_PAN     = 1,
	WAV_MIDI_CHANNEL = 2,
	WAV_PATCH_SAVE   = 3,
	WAV_PATCH_LOAD   = 4,
	WAV_VOLUME       = 5, /* output volume 0–3                          */
	WAV_SET_WAVE     = 6, /* followed by 16 bytes of wave RAM           */
	/* 7–31 reserved */
};

/* ---------------------------------------------------------------------- */
/* NOISE commands                                                          */
/* ---------------------------------------------------------------------- */

enum noise_cmd {
	NOISE_CHAN_VOLUME  = 0,
	NOISE_CHAN_PAN     = 1,
	NOISE_MIDI_CHANNEL = 2,
	NOISE_PATCH_SAVE   = 3,
	NOISE_PATCH_LOAD   = 4,
	NOISE_ATTACK       = 5,
	NOISE_DECAY        = 6,
	NOISE_SUSTAIN      = 7,
	NOISE_RELEASE      = 8,
	NOISE_VOLUME       = 9,  /* initial envelope volume 0–15            */
	NOISE_DIV          = 10, /* NR43 bits 2:0 — clock divider 0–7       */
	NOISE_WIDTH        = 11, /* NR43 bit 3 — LFSR: 0=15-bit, 1=7-bit   */
	/* 12–31 reserved */
};

/* ---------------------------------------------------------------------- */
/* Header byte helpers                                                     */
/* ---------------------------------------------------------------------- */

/** Build an instrument-specific header byte (V=0). */
static inline uint8_t proto_instr_hdr(enum instrument instr, uint8_t cmd)
{
	return ((uint8_t)instr << 5) | (cmd & 0x1f);
}

/** True if the header is instrument-specific (V=0). */
static inline int proto_is_instr(uint8_t hdr)
{
	return (hdr & 0x80) == 0;
}

/** Extract instrument from an instrument-specific header byte. */
static inline enum instrument proto_instr(uint8_t hdr)
{
	return (enum instrument)((hdr >> 5) & 0x03);
}

/** Extract command from an instrument-specific header byte. */
static inline uint8_t proto_cmd(uint8_t hdr)
{
	return hdr & 0x1f;
}

/* ---------------------------------------------------------------------- */
/* Receiver state machine (GB serial ISR)                                  */
/* ---------------------------------------------------------------------- */

/*
 * Embed an rx_buf in your application state and zero-initialise it.
 * Feed each received byte to proto_rx_byte(); it calls back into your
 * engine when a complete message is assembled.
 */
enum rx_state {
	RX_IDLE,     /* waiting for a header byte                          */
	RX_NOTE_HI,  /* got NOTE_ON; waiting for period[10:8] byte        */
	RX_NOTE_LO,  /* got period[10:8]; waiting for period[7:0] byte    */
	RX_VAL,      /* got instrument cmd; waiting for one value byte    */
	RX_WAVE,     /* got WAV_SET_WAVE; counting 16 wave RAM bytes      */
};

struct rx_buf {
	enum rx_state state;
	uint8_t       hdr; /* saved header byte                           */
	union {
		uint8_t period_hi; /* period[10:8] saved during RX_NOTE_LO  */
		uint8_t wave_idx;  /* next wave RAM byte index during RX_WAVE */
	};
};

#endif /* WAVES_PROTOCOL_H */
