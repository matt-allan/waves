/*
 * midilink.c — MIDI-to-gamelink protocol translator.
 *
 * Receives raw MIDI bytes one at a time via midilink_feed() and emits
 * zero or more gamelink protocol bytes for the Game Boy.
 */

#include "midilink.h"

#include <string.h>

/* ---------------------------------------------------------------------- */
/* Period table                                                            */
/*                                                                         */
/* GB APU period register values for MIDI notes 48 (C3) through 119 (B8). */
/* Derived from http://www.devrs.com/gb/files/sndtab.html                 */
/* ---------------------------------------------------------------------- */

const uint16_t midi_period_table[PERIOD_TABLE_LEN] = {
	  44,  156,  262,  363,  457,  547,  631,  710,  786,  854,  923,  986,
	1046, 1102, 1155, 1205, 1253, 1297, 1339, 1379, 1417, 1452, 1486, 1517,
	1546, 1575, 1602, 1627, 1650, 1673, 1694, 1714, 1732, 1750, 1767, 1783,
	1798, 1812, 1825, 1837, 1849, 1860, 1871, 1881, 1890, 1899, 1907, 1915,
	1923, 1930, 1936, 1943, 1949, 1954, 1959, 1964, 1969, 1974, 1978, 1982,
	1985, 1988, 1992, 1995, 1998, 2001, 2004, 2006, 2009, 2011, 2013, 2015,
};

/* ---------------------------------------------------------------------- */
/* Channel → instrument mapping                                           */
/* ---------------------------------------------------------------------- */

/**
 * Map a 1-based MIDI channel to a gamelink instrument.
 * Returns -1 if the channel is not assigned.
 */
static int8_t channel_to_instr(uint8_t midi_ch)
{
	switch (midi_ch) {
	case MIDI_CH_PU1:   return INSTR_PU1;
	case MIDI_CH_PU2:   return INSTR_PU2;
	case MIDI_CH_WAV:   return INSTR_WAV;
	case MIDI_CH_NOISE: return INSTR_NOISE;
	default:            return -1;
	}
}

/* ---------------------------------------------------------------------- */
/* Message handlers                                                        */
/* ---------------------------------------------------------------------- */

/**
 * Translate a parsed MIDI message into protocol bytes.
 * Returns the number of bytes written to @p out (0 on drop).
 */
static uint8_t translate(const midi_msg *msg, uint8_t *out, uint8_t out_cap)
{
	uint8_t type = midi_status_type(msg->status);

	/* Only handle channel voice messages. */
	if (type < MIDI_STATUS_NOTE_OFF || type > MIDI_STATUS_PITCH_BEND)
		return 0;

	uint8_t midi_ch = midi_status_channel(msg->status);
	int8_t instr = channel_to_instr(midi_ch);
	if (instr < 0)
		return 0;

	switch (type) {
	case MIDI_STATUS_NOTE_ON: {
		uint8_t note = msg->data[0];
		uint8_t vel  = msg->data[1];

		/* Velocity 0 is equivalent to NOTE_OFF per MIDI spec. */
		if (vel == 0) {
			if (out_cap < 1)
				return 0;
			out[0] = proto_hdr((enum instrument)instr,
			                   MCU_NOTE_OFF);
			return 1;
		}

		/* Clamp note to the period table range. */
		if (note < MIDI_NOTE_MIN || note > MIDI_NOTE_MAX)
			return 0;

		if (out_cap < 3)
			return 0;

		uint16_t period =
			midi_period_table[note - MIDI_NOTE_MIN];
		out[0] = proto_hdr((enum instrument)instr, MCU_NOTE_ON);
		out[1] = (uint8_t)(period >> 8);
		out[2] = (uint8_t)(period & 0xFF);
		return 3;
	}

	case MIDI_STATUS_NOTE_OFF: {
		if (out_cap < 1)
			return 0;
		out[0] = proto_hdr((enum instrument)instr, MCU_NOTE_OFF);
		return 1;
	}

	default:
		return 0;
	}
}

/* ---------------------------------------------------------------------- */
/* Public API                                                              */
/* ---------------------------------------------------------------------- */

void midilink_init(struct midilink *ml)
{
	memset(ml, 0, sizeof(*ml));
}

uint8_t midilink_feed(struct midilink *ml, uint8_t byte,
                      uint8_t *out, uint8_t out_cap)
{
	/*
	 * midigram shares the msg struct across calls.  Real-time messages
	 * (clock, start, etc.) can arrive mid-message and overwrite
	 * msg.status while data bytes are still pending.  We keep the msg
	 * in our context so data bytes accumulate correctly, and save the
	 * in-progress status so we can restore it after an RT interruption.
	 */
	uint8_t saved_status = ml->msg.status;

	if (!midi_parse(&ml->midi, byte, &ml->msg))
		return 0;

	uint8_t type = midi_status_type(ml->msg.status);

	/* Real-time messages: ignore and restore the in-progress status. */
	if (type == MIDI_STATUS_SYSTEM && ml->msg.status >= 0xF8) {
		ml->msg.status = saved_status;
		return 0;
	}

	return translate(&ml->msg, out, out_cap);
}
