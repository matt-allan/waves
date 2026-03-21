/*
 * protocol.h — wire protocol for the Game Boy ↔ MCU link port serial connection.
 *
 * Every message starts with a header byte:
 *
 *   7   6   5   4   3   2   1   0
 *  [II  II  CCC CCC DDD DDD DDD]
 *
 *  II  (bits 7:6) — instrument index (0=PU1, 1=PU2, 2=WAV, 3=NOISE)
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

enum instrument {
	INSTR_PU1   = 0,
	INSTR_PU2   = 1,
	INSTR_WAV   = 2,
	INSTR_NOISE = 3,
};

/* ---------------------------------------------------------------------- */
/* Commands                                                                 */
/* ---------------------------------------------------------------------- */

/*
 * 3 bits → 8 slots; 5 are used.  Direction is always known from context;
 * SET_PARAM and HANDSHAKE share the same code in both directions.
 *
 * MCU → GB: NOTE_ON, NOTE_OFF, SET_PARAM, HANDSHAKE
 * GB  → MCU: SET_PARAM, MIDI_ASSIGN, HANDSHAKE (as ACK)
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
	 * MCU → GB: used during boot (patch load) and for MIDI CC updates.
	 * GB  → MCU: used when the user saves a patch; GB sends one message per
	 *            parameter for the full patch.
	 */
	CMD_SET_PARAM = 2,

	/*
	 * HANDSHAKE — link-up announcement / acknowledgement.
	 *   Header: [00 011 000]  (II = 0, ignored)
	 *   No payload.
	 *
	 * MCU sends HANDSHAKE first.  GB responds with the same byte as an ACK.
	 * The GB starts a timeout on boot; if HANDSHAKE is not received within
	 * ~500 ms it enters standalone mode with default patches.
	 */
	CMD_HANDSHAKE = 3,

	/*
	 * MIDI_ASSIGN — notify MCU of a MIDI channel assignment change.
	 *   Header: [II 100 000]
	 *   Byte 1: MIDI channel (0–15)
	 *
	 * Sent immediately when the user changes the MIDI channel for an
	 * instrument in the UI.  The MCU updates its routing table.
	 */
	CMD_MIDI_ASSIGN = 4,

	/* 5–7 reserved */
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
	RX_IDLE,       /* waiting for a header byte                         */
	RX_NOTE_ON,    /* header saved; waiting for period low byte         */
	RX_PARAM_ID,   /* header saved; waiting for param_id               */
	RX_PARAM_VAL,  /* header + param_id saved; waiting for value       */
	RX_MIDI_ASSIGN, /* header saved; waiting for midi_channel byte     */
};

struct rx_buf {
	enum rx_state state;
	uint8_t       hdr;      /* saved header byte                        */
	uint8_t       param_id; /* saved param_id for SET_PARAM             */
};

#endif /* WAVES_PROTOCOL_H */
