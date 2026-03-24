#ifndef MIDIGRAM_H
#define MIDIGRAM_H

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stdint.h>

	/**
	 * Implementation notes:
	 *
	 * - Each message is 1-3 bytes (except sysex, and "running status")
	 * - The first byte is the "status" which indicates the type of the
	 * message
	 * - The optional second and third bytes are the "data" bytes
	 * - The MSB of the status byte is always set ("1")
	 * - Running status is for voice and mode messages only
	 * - Real time messages don't affect running status
	 * - Unknown status bytes should be ignored
	 * - Real time messages have no data bytes
	 * - The MSB of data bytes is always 0
	 *
	 *
	 * https://midi.org/expanded-midi-1-0-messages-list
	 *
	 */

	/**
	 * High bytes for midi status codes.
	 *
	 * @see https://midi.org/expanded-midi-1-0-messages-list
	 */
	typedef enum
	{
		/**
		 * Channel note off
		 */
		MIDI_STATUS_NOTE_OFF = 0x80,
		/**
		 * Channel note on
		 */
		MIDI_STATUS_NOTE_ON = 0x90,
		/**
		 * Channel polyphonic aftertouch
		 */
		MIDI_STATUS_POLY_AT = 0xA0,
		/**
		 * Channel control / mode change
		 */
		MIDI_STATUS_CC = 0xB0,
		/**
		 * Channel program change
		 */
		MIDI_STATUS_PC = 0xC0,
		/**
		 * Channel aftertouch
		 */
		MIDI_STATUS_AT = 0xD0,
		/**
		 * Channel pitchbend change
		 */
		MIDI_STATUS_PITCH_BEND = 0xE0,
		/**
		 * System messages
		 */
		MIDI_STATUS_SYSTEM = 0xF0,
	} midi_status;

	/**
	 * MIDI system messages.
	 */
	typedef enum
	{
		/**
		 * System Exclusive
		 */
		MIDI_STATUS_SYS_SYSEX = 0xF0,
		/**
		 * MIDI Time Code Qtr. Frame
		 */
		MIDI_STATUS_SYS_MTC_QTR_FRAME = 0xF1,
		/**
		 * Song Position Pointer
		 */
		MIDI_STATUS_SYS_SONG_POS_PTR = 0xF2,
		/**
		 * Song Select (Song #)
		 */
		MIDI_STATUS_SYS_SONG_SELECT = 0xF3,
		/**
		 * Tune request
		 */
		MIDI_STATUS_SYS_TUNE_REQ = 0xF6,
		/**
		 * End of SysEx (EOX)
		 */
		MIDI_STATUS_SYS_EOX = 0xF7,
		/**
		 * Timing clock
		 */
		MIDI_STATUS_SYS_TIMING_CLOCK = 0xF8,
		/**
		 * Start
		 */
		MIDI_STATUS_SYS_START = 0xFA,
		/**
		 * Continue
		 */
		MIDI_STATUS_SYS_CONTINUE = 0xFB,
		/**
		 * Stop
		 */
		MIDI_STATUS_SYS_STOP = 0xFC,
		/**
		 * Active Sensing
		 */
		MIDI_STATUS_SYS_ACTIVE_SENSING = 0xFE,
		/**
		 * System Reset
		 */
		MIDI_STATUS_SYS_RESET = 0xFF,

	} midi_status_system;

	/**
	 * The current state of the MIDI parser.
	 */
	typedef enum
	{
		/** status byte */
		MIDI_PARSE_STATUS,
		/** first data byte */
		MIDI_PARSE_DATA_0,
		/** second data byte */
		MIDI_PARSE_DATA_1,
		/** sysex data */
		MIDI_PARSE_SYSEX,
	} midi_parse_state;

	/**
	 * Context for a midi connection.
	 */
	typedef struct midi_context
	{
		/**
		 * The current parsing state.
		 */
		midi_parse_state parse_state;

		/**
		 * The last channel (voice or mode / non-system) status parsed.
		 */
		uint8_t running_status;

		/**
		 * Caller-provided buffer for SysEx data bytes (excluding
		 * 0xF0/EOX). May be NULL to discard SysEx.
		 */
		uint8_t *sysex_buf;

		/**
		 * Capacity of sysex_buf in bytes.
		 */
		uint16_t sysex_cap;

		/**
		 * Number of SysEx data bytes seen so far, including any that
		 * exceeded sysex_cap. Compare against sysex_cap to
		 * detect overflow.
		 */
		uint16_t sysex_len;

		/**
		 * Expected data byte count for the message currently being
		 * parsed. Mirrors midi_msg.data_len across calls.
		 */
		int8_t data_len;
	} midi_context;

	typedef struct midi_msg
	{
		/**
		 * The status byte.
		 *
		 * @see https://midi.org/expanded-midi-1-0-messages-list
		 */
		uint8_t status;

		/**
		 * The data bytes.
		 *
		 */
		uint8_t data[2];

		/**
		 * The number of data bytes expected for the status.
		 */
		int8_t data_len;
	} midi_msg;

	/**
	 * Parse a message from a MIDI byte sequence.
	 **/
	bool midi_parse(struct midi_context *ctx, const uint8_t byte,
	                midi_msg *msg);

	/**
	 * Extract the status type from a status byte.
	 */
	static inline uint8_t midi_status_type(const uint8_t byte)
	{
		return (byte & 0xF0);
	}

	/**
	 * Extract the channel from a status byte.
	 */
	static inline uint8_t midi_status_channel(const uint8_t byte)
	{
		return (byte & 0x0F) + 1;
	}

#ifdef __cplusplus
}
#endif

#endif // #ifndef MIDIGRAM_H
