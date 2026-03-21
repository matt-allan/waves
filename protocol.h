/*
 * protocol.h — wire protocol for the Game Boy ↔ MCU link port serial connection.
 *
 * The two directions use different header formats.
 *
 * MCU → GB header byte:
 *
 *   7   6   5   4   3   2   1   0
 *  [II  II  CCC CCC DDD DDD DDD]
 *
 *  II  (bits 7:6) — instrument index (0=PU1, 1=PU2, 2=WAV, 3=NOISE)
 *  CCC (bits 5:3) — command
 *  DDD (bits 2:0) — inline data (command-specific; 0 unless noted)
 *
 * For NOTE_ON, DDD carries period[10:8] so the full note event fits in
 * 2 bytes rather than 3.  For all other commands DDD is reserved (0).
 *
 * GB → MCU header byte:
 *
 *   7   6   5   4   3   2   1   0
 *  [V   II  II  CC  CC  CC  CC  CC]
 *
 *  V  (bit 7)    — 0 = instrument-specific, 1 = global (TBD)
 *  II (bits 6:5) — instrument (when V=0): 0=PU1, 1=PU2, 2=WAV, 3=NOISE
 *  CC (bits 4:0) — command (instrument-specific namespace)
 *
 * Commands 0–4 are common to every instrument (same meaning, same ID).
 * Commands 5+ are instrument-specific.
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
/* MCU → GB commands                                                       */
/* ---------------------------------------------------------------------- */

enum mcu_cmd {
	/*
	 * NOTE_ON — trigger a note on the given instrument.
	 *   Header: [II 000 PPP]  where PPP = period[10:8]
	 *   Byte 1: period[7:0]
	 *
	 * For INSTR_NOISE, period[10:8] is unused (set to 0) and byte 1 is
	 * the raw NR43 value.  The MCU pre-computes NR43 from the MIDI note.
	 */
	MCU_NOTE_ON  = 0,

	/*
	 * NOTE_OFF — release the note on the given instrument.
	 *   Header: [II 001 000]
	 *   No payload.
	 */
	MCU_NOTE_OFF = 1,

	/*
	 * SET_PARAM — update one patch parameter.
	 *   Header: [II 010 000]
	 *   Byte 1: param_id  (enum mcu_param)
	 *   Byte 2: value
	 *
	 * Streams the full patch state on boot and forwards MIDI CC updates
	 * at runtime.
	 */
	MCU_SET_PARAM = 2,

	/* 3–7 reserved */
};

/*
 * MCU → GB param IDs (byte 1 of SET_PARAM payload).
 * These use a flat global namespace; the instrument from the header
 * disambiguates where the same ID is shared (e.g. ATTACK).
 */
enum mcu_param {
	MCU_PARAM_ATTACK      = 0,  /* envelope attack pace 1–7             */
	MCU_PARAM_DECAY       = 1,  /* envelope decay pace 1–7              */
	MCU_PARAM_SUSTAIN     = 2,  /* sustain volume level 0–15            */
	MCU_PARAM_RELEASE     = 3,  /* envelope release pace 1–7            */
	MCU_PARAM_DUTY_CYCLE  = 4,  /* duty cycle 0–3; PU1, PU2            */
	MCU_PARAM_SWEEP_PACE  = 5,  /* sweep pace 0–7 (0=off); PU1         */
	MCU_PARAM_SWEEP_DIR   = 6,  /* sweep dir 0=up 1=down; PU1          */
	MCU_PARAM_SWEEP_STEP  = 7,  /* sweep step magnitude 0–7; PU1       */
	MCU_PARAM_VOLUME      = 8,  /* output volume: 0–3 WAV, 0–15 NOISE  */
	MCU_PARAM_WAVE_0      = 9,  /* WAV wave RAM byte 0 (bytes 1–15: +i) */
	/* MCU_PARAM_WAVE_1 through MCU_PARAM_WAVE_15 occupy IDs 10–24     */
	MCU_PARAM_NOISE_DIV   = 25, /* NR43 bits 2:0 — clock divider 0–7   */
	MCU_PARAM_NOISE_WIDTH = 26, /* NR43 bit 3 — LFSR: 0=15-bit, 1=7-bit */
	MCU_PARAM_CHAN_VOLUME  = 27, /* mixer output volume 0–7             */
	MCU_PARAM_CHAN_PAN    = 28, /* pan: 0=left, 1=both, 2=right         */
	MCU_PARAM_MIDI_CHANNEL = 29, /* MIDI channel assignment 0–15        */
};

/* ---------------------------------------------------------------------- */
/* MCU → GB header helpers                                                 */
/* ---------------------------------------------------------------------- */

/** Build a MCU → GB header byte. */
static inline uint8_t mcu_hdr(enum instrument instr, enum mcu_cmd cmd,
			       uint8_t data)
{
	return ((uint8_t)instr << 6) | ((uint8_t)cmd << 3) | (data & 0x07);
}

/** Extract instrument from a MCU → GB header byte. */
static inline enum instrument mcu_hdr_instr(uint8_t hdr)
{
	return (enum instrument)(hdr >> 6);
}

/** Extract command from a MCU → GB header byte. */
static inline enum mcu_cmd mcu_hdr_cmd(uint8_t hdr)
{
	return (enum mcu_cmd)((hdr >> 3) & 0x07);
}

/** Extract inline data bits from a MCU → GB header byte. */
static inline uint8_t mcu_hdr_data(uint8_t hdr)
{
	return hdr & 0x07;
}

/* ---------------------------------------------------------------------- */
/* GB → MCU commands                                                       */
/* ---------------------------------------------------------------------- */

/*
 * Commands 0–4 are common to every instrument (same meaning, same ID).
 * Commands 5+ are instrument-specific; see per-instrument enums below.
 */
enum common_cmd {
	CMD_CHAN_VOLUME  = 0, /* mixer output volume 0–7                    */
	CMD_CHAN_PAN     = 1, /* pan: 0=left, 1=both, 2=right               */
	CMD_MIDI_CHANNEL = 2, /* MIDI channel assignment 0–15               */
	CMD_PATCH_SAVE   = 3, /* save current params as patch N             */
	CMD_PATCH_LOAD   = 4, /* load patch N and stream all params to GB   */
	/* 5–31: instrument-specific (see per-instrument enums)             */
};

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
	/* 13–31 reserved */
};

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
/* GB → MCU header helpers                                                 */
/* ---------------------------------------------------------------------- */

/** Build a GB → MCU instrument-specific header byte (V=0). */
static inline uint8_t gb_hdr(enum instrument instr, uint8_t cmd)
{
	return ((uint8_t)instr << 5) | (cmd & 0x1f);
}

/** True if a GB → MCU header is instrument-specific (V=0). */
static inline int gb_hdr_is_instr(uint8_t hdr)
{
	return (hdr & 0x80) == 0;
}

/** Extract instrument from a GB → MCU instrument-specific header byte. */
static inline enum instrument gb_hdr_instr(uint8_t hdr)
{
	return (enum instrument)((hdr >> 5) & 0x03);
}

/** Extract command from a GB → MCU instrument-specific header byte. */
static inline uint8_t gb_hdr_cmd(uint8_t hdr)
{
	return hdr & 0x1f;
}

/* ---------------------------------------------------------------------- */
/* Receiver state machine (GB serial ISR, MCU → GB direction)             */
/* ---------------------------------------------------------------------- */

/*
 * Embed an rx_buf in your application state and zero-initialise it.
 * Feed each received byte to the ISR; it dispatches on rx.state to
 * assemble multi-byte messages before acting on them.
 */
enum rx_state {
	RX_IDLE,      /* waiting for a header byte                          */
	RX_NOTE_ON,   /* header saved; waiting for period low byte          */
	RX_PARAM_ID,  /* header saved; waiting for param_id                 */
	RX_PARAM_VAL, /* header + param_id saved; waiting for value         */
};

struct rx_buf {
	enum rx_state state;
	uint8_t       hdr;      /* saved header byte                        */
	uint8_t       param_id; /* saved param_id for SET_PARAM             */
};

#endif /* WAVES_PROTOCOL_H */
