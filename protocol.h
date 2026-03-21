/*
 * protocol.h — wire protocol for the Game Boy ↔ MCU link port serial connection.
 *
 * Every message starts with a header byte:
 *
 *   7   6   5   4   3   2   1   0
 *  [II  II  CCC CCC DDD DDD DDD]
 *
 *  II  (bits 7:6) — instrument selector.  See enum instrument above.
 *                   For NOTE_ON/NOTE_OFF: bitmask (bit7=PU2, bit6=PU1).
 *                   For SET_PARAM: exactly one channel.
 *  CCC (bits 5:3) — command
 *  DDD (bits 2:0) — inline data (command-specific; 0 unless noted)
 *
 * For NOTE_ON, DDD carries period[10:8] so the full note event fits in 2 bytes
 * rather than 3.  For all other commands DDD is reserved and must be 0.
 *
 * This file is plain C99 and is shared by the GB ROM (SDCC) and the MCU side.
 */
#ifndef WAVES_PROTOCOL_H
#define WAVES_PROTOCOL_H

#include <stdint.h>

/* ---------------------------------------------------------------------- */
/* Instruments                                                              */
/* ---------------------------------------------------------------------- */

/*
 * For NOTE_ON and NOTE_OFF the II field is a bitmask: bit 6 = PU1, bit 7 =
 * PU2.  Setting both bits addresses both pulse channels simultaneously, which
 * lets the MCU trigger a unison note in a single 2-byte message.
 *
 * WAV is addressed by II = 0b00 (neither PU bit set).
 *
 * For SET_PARAM exactly one channel must be targeted, so only the single-
 * channel values below are valid in that command.
 *
 * NOISE is not yet assigned; the channel is not implemented.
 */
enum instrument {
	INSTR_WAV = 0, /* 0b00 — addressed by value, not a bitmask bit */
	INSTR_PU1 = 1, /* 0b01 — bitmask bit 0                         */
	INSTR_PU2 = 2, /* 0b10 — bitmask bit 1                         */
	/* INSTR_NOISE — TBD; NOISE channel not yet implemented */
};

/* ---------------------------------------------------------------------- */
/* Commands                                                                 */
/* ---------------------------------------------------------------------- */

/*
 * Three commands cover the full protocol.  Direction is always known from
 * context; SET_PARAM is used in both directions.
 *
 * MCU → GB: NOTE_ON, NOTE_OFF, SET_PARAM
 * GB  → MCU: SET_PARAM
 *
 * No handshake is needed.  The GB is a pure slave: its ISR processes
 * whatever arrives.  The MCU streams the full patch state on boot and
 * sends note/param events at runtime; no coordination ceremony is required.
 */
enum cmd {
	/*
	 * NOTE_ON — trigger a note on the given instrument.
	 *   Header: [II 000 PPP]  where PPP = period[10:8]
	 *   Byte 1: period[7:0]
	 *
	 * For INSTR_NOISE, period[10:8] is unused (set to 0) and byte 1 is the
	 * raw NR43 register value (clock shift, LFSR width, clock divider).
	 * The MCU pre-computes NR43 from the MIDI note number.
	 */
	CMD_NOTE_ON = 0,

	/*
	 * NOTE_OFF — release the note on the given instrument.
	 *   Header: [II 001 000]
	 *   No payload.
	 */
	CMD_NOTE_OFF = 1,

	/*
	 * SET_PARAM — update one patch parameter.
	 *   Header: [II 010 000]
	 *   Byte 1: param_id  (enum param_id)
	 *   Byte 2: value     (uint8_t, clamped by receiver to valid range)
	 *
	 * MCU → GB: streams the full patch state on boot and forwards MIDI CC
	 *           updates at runtime.  PARAM_MIDI_CHANNEL tells the GB which
	 *           MIDI channel each instrument is assigned to (for display).
	 * GB  → MCU: sends one message per parameter when the user saves a
	 *           patch.  PARAM_MIDI_CHANNEL is sent immediately when the
	 *           user changes the assignment so the MCU can update routing.
	 */
	CMD_SET_PARAM = 2,

	/* 3–7 reserved */
};

/* ---------------------------------------------------------------------- */
/* Patch parameter IDs (SET_PARAM payload)                                 */
/* ---------------------------------------------------------------------- */

enum param_id {
	PARAM_ATTACK      = 0, /* envelope attack pace  1–7; all ADSR instruments  */
	PARAM_DECAY       = 1, /* envelope decay pace   1–7                        */
	PARAM_SUSTAIN     = 2, /* sustain volume level  0–15 (absolute)            */
	PARAM_RELEASE     = 3, /* envelope release pace 1–7                        */
	PARAM_DUTY_CYCLE  = 4, /* duty cycle 0–3 (12.5/25/50/75%); PU1, PU2       */
	PARAM_SWEEP_PACE  = 5, /* frequency sweep pace  0–7 (0 = off); PU1 only   */
	PARAM_SWEEP_DIR   = 6, /* sweep direction 0=increase 1=decrease; PU1 only */
	PARAM_SWEEP_STEP  = 7, /* sweep step magnitude  0–7; PU1 only             */
	PARAM_VOLUME      = 8, /* output volume: 0–3 for WAV, 0–15 for NOISE      */
	PARAM_WAVE_0      = 9, /* WAV wave RAM byte 0; byte i = PARAM_WAVE_0 + i  */
	/* PARAM_WAVE_1 through PARAM_WAVE_15 occupy IDs 10–24 */
	PARAM_NOISE_DIV   = 25, /* NR43 bits 2:0 — clock divider 0–7              */
	PARAM_NOISE_WIDTH = 26, /* NR43 bit  3   — LFSR width: 0=15-bit, 1=7-bit  */
	PARAM_CHAN_VOLUME  = 27, /* mixer: per-instrument volume 0–7               */
	PARAM_CHAN_PAN    = 28, /* mixer: pan 0=left, 1=both, 2=right              */
	PARAM_MIDI_CHANNEL = 29, /* MIDI channel assignment 0–15                  */
};

/* ---------------------------------------------------------------------- */
/* Header byte helpers                                                      */
/* ---------------------------------------------------------------------- */

/** Build a header byte. */
static inline uint8_t proto_header(enum instrument instr, enum cmd cmd,
				   uint8_t data)
{
	return ((uint8_t)instr << 6) | ((uint8_t)cmd << 3) | (data & 0x07);
}

/** Extract instrument from a header byte. */
static inline enum instrument proto_instr(uint8_t hdr)
{
	return (enum instrument)(hdr >> 6);
}

/** Extract command from a header byte. */
static inline enum cmd proto_cmd(uint8_t hdr)
{
	return (enum cmd)((hdr >> 3) & 0x07);
}

/** Extract inline data bits from a header byte. */
static inline uint8_t proto_data(uint8_t hdr)
{
	return hdr & 0x07;
}

/* ---------------------------------------------------------------------- */
/* Receiver state machine (GB serial ISR)                                  */
/* ---------------------------------------------------------------------- */

/*
 * Embed an rx_buf in your application state and zero-initialise it.
 * Feed each received byte to proto_rx_byte(); it calls back into your
 * engine functions when a complete message is assembled.
 *
 * The state machine holds the minimum context needed between bytes:
 * - one header byte (instrument + command + inline data)
 * - one param_id byte for SET_PARAM
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
