/*
 * midilink.h — translate MIDI byte stream into gamelink serial protocol.
 *
 * Feed raw MIDI bytes one at a time; get back zero or more protocol bytes
 * to send over the Game Boy link port.  Designed for use in a UART ISR on
 * a low-power MCU.
 *
 * Plain C99, no dynamic allocation, no blocking.
 */
#ifndef WAVES_MIDILINK_H
#define WAVES_MIDILINK_H

#include <stdbool.h>
#include <stdint.h>

#include "midigram.h"
#include "protocol.h"

/* ---------------------------------------------------------------------- */
/* Note-to-period lookup                                                   */
/* ---------------------------------------------------------------------- */

/** Lowest MIDI note in the period table (C3). */
enum { MIDI_NOTE_MIN = 48 };

/** Highest MIDI note in the period table (B8). */
enum { MIDI_NOTE_MAX = 119 };

/** Number of entries in the period table. */
enum { PERIOD_TABLE_LEN = MIDI_NOTE_MAX - MIDI_NOTE_MIN + 1 };

/** GB period register values, indexed by (midi_note - MIDI_NOTE_MIN). */
extern const uint16_t midi_period_table[PERIOD_TABLE_LEN];

/* ---------------------------------------------------------------------- */
/* Fixed MIDI channel → instrument mapping (1-based channels)             */
/* ---------------------------------------------------------------------- */

enum {
	MIDI_CH_PU1   = 1,
	MIDI_CH_PU2   = 2,
	MIDI_CH_WAV   = 3,
	MIDI_CH_NOISE = 10,
};

/* ---------------------------------------------------------------------- */
/* Context                                                                 */
/* ---------------------------------------------------------------------- */

/**
 * Midilink translator context.
 *
 * Zero-initialise before first use, or call midilink_init().
 */
struct midilink {
	struct midi_context midi; /* midigram parser state */
};

/* ---------------------------------------------------------------------- */
/* API                                                                     */
/* ---------------------------------------------------------------------- */

/** Initialise (or reset) a midilink context. */
void midilink_init(struct midilink *ml);

/**
 * Feed one MIDI byte and collect any resulting protocol bytes.
 *
 * @param ml      Translator context.
 * @param byte    Raw MIDI byte from UART.
 * @param out     Caller-provided output buffer.
 * @param out_cap Capacity of @p out in bytes.
 * @return        Number of protocol bytes written to @p out (0–3).
 */
uint8_t midilink_feed(struct midilink *ml, uint8_t byte,
                      uint8_t *out, uint8_t out_cap);

#endif /* WAVES_MIDILINK_H */
