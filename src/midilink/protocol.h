/*
 * protocol.h — wire protocol for the Game Boy ↔ MCU link port serial connection.
 *
 * Both directions share the same header byte format:
 *
 *   7   6   5   4   3   2   1   0
 *  [V   II  II  CC  CC  CC  CC  CC]
 *
 *  V  (bit 7)    — 0 = instrument-specific, 1 = global (TBD)
 *  II (bits 6:5) — instrument: 0=PU1, 1=PU2, 2=WAV, 3=NOISE
 *  CC (bits 4:0) — command
 *
 * Command slot layout (5 bits = 32 slots):
 *
 *  Slots 0–1:   direction-specific control (NOTE_ON/OFF vs PATCH_SAVE/LOAD)
 *  Slots 2–9:   common params, same meaning both directions
 *  Slots 10–24: free
 *  Slots 25–31: instrument-specific, per-instrument meaning
 *
 * Payload:
 *  NOTE_ON:    2 bytes — period[10:8] then period[7:0]
 *  NOTE_OFF:   no payload
 *  PATCH_SAVE: 1 byte — patch number
 *  PATCH_LOAD: 1 byte — patch number
 *  SET_WAVE:   16 bytes — wave RAM, written directly to 0xFF30–0xFF3F
 *  all others: 1 byte — value
 *
 * Register write optimisations (MCU pre-formats these for direct GB write):
 *  DUTY_CYCLE  value = NR11/NR21 duty bits pre-shifted to bits 7:6
 *  WAV_VOLUME  value = NR32 volume bits pre-shifted to bits 6:5
 *  SWEEP       value = full NR10 byte
 *  NOISE_CTRL  value = NR43[3:0] (LFSR width + clock divider)
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
/* Direction-specific commands (slots 0–1)                                 */
/* ---------------------------------------------------------------------- */

enum mcu_cmd {
	MCU_NOTE_ON  = 0, /* 2 payload bytes: period[10:8], period[7:0]    */
	MCU_NOTE_OFF = 1, /* no payload                                     */
};

enum gb_cmd {
	GB_PATCH_SAVE = 0, /* 1 payload byte: patch number                  */
	GB_PATCH_LOAD = 1, /* 1 payload byte: patch number                  */
};

/* ---------------------------------------------------------------------- */
/* Common commands (slots 2–9, same meaning both directions)               */
/* ---------------------------------------------------------------------- */

enum common_cmd {
	CMD_CHAN_VOLUME  = 2, /* mixer output volume 0–7; all instruments    */
	CMD_CHAN_PAN     = 3, /* pan 0=left 1=both 2=right; all instruments  */
	CMD_MIDI_CHANNEL = 4, /* MIDI channel 0–15; all instruments          */
	CMD_ATTACK       = 5, /* envelope attack pace 1–7; PU1, PU2, NOISE  */
	CMD_DECAY        = 6, /* envelope decay pace 1–7; PU1, PU2, NOISE   */
	CMD_SUSTAIN      = 7, /* sustain volume 0–15; PU1, PU2, NOISE       */
	CMD_RELEASE      = 8, /* envelope release pace 1–7; PU1, PU2, NOISE */
	CMD_VOLUME       = 9, /* output volume; WAV (NR32 pre-shifted), NOISE */
	/* 10–24: free */
};

/* ---------------------------------------------------------------------- */
/* Instrument-specific commands (slots 25–31)                              */
/* ---------------------------------------------------------------------- */

enum pu1_cmd {
	PU1_DUTY_CYCLE = 25, /* duty 0–3, pre-shifted to NR11 bits 7:6      */
	PU1_SWEEP      = 26, /* full NR10 byte, written directly             */
	/* 27–31 reserved */
};

enum pu2_cmd {
	PU2_DUTY_CYCLE = 25, /* duty 0–3, pre-shifted to NR21 bits 7:6      */
	/* 26–31 reserved */
};

enum wav_cmd {
	WAV_SET_WAVE = 25, /* 16 payload bytes, written directly to wave RAM */
	/* 26–31 reserved */
};

enum noise_cmd {
	NOISE_CTRL = 25, /* NR43[3:0]: LFSR width (bit 3) + divider (bits 2:0) */
	/* 26–31 reserved */
};

/* ---------------------------------------------------------------------- */
/* Header byte helpers (same format both directions)                       */
/* ---------------------------------------------------------------------- */

/** Build an instrument-specific header byte (V=0) — macro for use in
 *  static initializers where SDCC cannot evaluate inline functions. */
#define PROTO_HDR(instr, cmd) (((instr) << 5) | ((cmd) & 0x1f))

/** Build an instrument-specific header byte (V=0). */
static inline uint8_t proto_hdr(enum instrument instr, uint8_t cmd)
{
	return PROTO_HDR(instr, cmd);
}

/** True if the header is instrument-specific (V=0). */
static inline int proto_is_instr(uint8_t hdr)
{
	return (hdr & 0x80) == 0;
}

/** Extract instrument from a header byte. */
static inline enum instrument proto_instr(uint8_t hdr)
{
	return (enum instrument)((hdr >> 5) & 0x03);
}

/** Extract command from a header byte. */
static inline uint8_t proto_cmd(uint8_t hdr)
{
	return hdr & 0x1f;
}

/* ---------------------------------------------------------------------- */
/* Receiver state machine (GB side, MCU → GB messages)                    */
/* ---------------------------------------------------------------------- */

enum rx_state {
	RX_IDLE,     /* waiting for a header byte                          */
	RX_NOTE_HI,  /* got NOTE_ON; waiting for period[10:8] byte        */
	RX_NOTE_LO,  /* got period[10:8]; waiting for period[7:0] byte    */
	RX_VAL,      /* got param cmd; waiting for one value byte         */
	RX_WAVE,     /* got WAV_SET_WAVE; counting 16 wave RAM bytes      */
};

struct rx_buf {
	enum rx_state state;
	uint8_t       hdr;       /* saved header byte                      */
	union {
		uint8_t period_hi; /* period[10:8] saved during RX_NOTE_LO */
		uint8_t wave_idx;  /* next wave RAM index during RX_WAVE    */
	};
};

#endif /* WAVES_PROTOCOL_H */
