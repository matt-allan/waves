#include "midigram.h"
#include <stdint.h>

/**
 * Checks if this is a status byte.
 */
static inline bool is_status_byte(uint8_t byte) { return byte >= 0x80; }

/**
 * Checks if this is a status byte for a system message.
 * Note that system realtime messages are included.
 */
static inline bool is_sys_byte(uint8_t byte)
{
	return byte >= MIDI_STATUS_SYSTEM;
}

/**
 * Checks if this is a status byte for a system realtime message.
 */
static inline bool is_sys_rt_byte(uint8_t byte)
{
	return byte >= MIDI_STATUS_SYS_TIMING_CLOCK;
}

/**
 * Returns the number of data bytes expected for the given status.
 */
static int8_t data_bytes_len(uint8_t status_byte)
{
	// note on, note off, polyphonic AT, CC
	if (status_byte < 0xC0)
	{
		return 2;
	}

	// PC, CH aftertouch
	if (status_byte < 0xE0)
	{
		return 1;
	}

	// pitch bend
	if (status_byte < 0xF0)
	{
		return 2;
	}

	switch (status_byte)
	{
	case 0xF0: // sysex
		return -1;
	case 0xF1: // midi time code
		return 1;
	case 0xF2: // song position pointer
		return 2;
	case 0xF3: // song select
		return 1;
	default: // EOX, tune, realtime, etc.
		return 0;
	}
}

bool midi_parse(struct midi_context *ctx, const uint8_t next_byte,
                midi_msg *msg)
{
	if (!ctx || !msg)
		return false;

	bool is_status = is_status_byte(next_byte);
	bool is_rt = is_status && is_sys_rt_byte(next_byte);

	// If it's a system realtime message, we have to handle it immediately,
	// even if we are in the middle of parsing a different message. The
	// state of the parser will not change but a message will be returned.
	if (is_rt)
	{
		// check for reserved / undefined status bytes
		if (next_byte == 0xF9 || next_byte == 0xFD)
		{
			goto error;
		}

		msg->status = next_byte;
		msg->data_len = 0;

		return true;
	}

	// EOX terminates an in-progress SysEx and returns the buffered data.
	if (next_byte == MIDI_STATUS_SYS_EOX &&
	    ctx->parse_state == MIDI_PARSE_SYSEX)
	{
		msg->status = MIDI_STATUS_SYS_EOX;
		msg->data_len = -1;
		ctx->parse_state = MIDI_PARSE_STATUS;
		ctx->status = 0;
		return true;
	}

	// If it's any other status byte, we need to handle it, even if that
	// means discarding an in-progress message.
	if (is_status)
	{
		// check for reserved / undefined status bytes
		if (next_byte == 0xF4 || next_byte == 0xF5)
		{
			goto error;
		}

		// update the msg and the parse state
		int8_t len = data_bytes_len(next_byte);

		msg->status = next_byte;
		msg->data_len = len;
		ctx->data_len = len;

		switch (len)
		{
		case -1:
			ctx->parse_state = MIDI_PARSE_SYSEX;
			ctx->sysex_len = 0;
			ctx->status = 0;
			return false;
		case 1:
		case 2:
			ctx->parse_state = MIDI_PARSE_DATA_0;
			ctx->status = next_byte;
			return false;
		default:
			// It must be a non-RT sys. message if it has no data
			// bytes
			ctx->parse_state = MIDI_PARSE_STATUS;
			ctx->status = 0;
			return true;
		}
	}

	// if we were waiting for a status byte but we have a running status,
	// set the status byte and immediately move to parsing data bytes
	if (ctx->parse_state == MIDI_PARSE_STATUS && ctx->status)
	{
		// update the msg and the parse state
		int8_t len = data_bytes_len(ctx->status);

		msg->status = ctx->status;
		msg->data_len = len;
		ctx->data_len = len;

		ctx->parse_state = MIDI_PARSE_DATA_0;
	}

	switch (ctx->parse_state)
	{
	case MIDI_PARSE_DATA_0:
		msg->status = ctx->status;
		msg->data[0] = next_byte;
		msg->data_len = ctx->data_len;

		if (ctx->data_len == 1)
		{
			ctx->parse_state = MIDI_PARSE_STATUS;

			if (ctx->status >= MIDI_STATUS_SYSTEM)
			{
				ctx->status = 0;
			}

			return true;
		}
		else
		{
			ctx->parse_state = MIDI_PARSE_DATA_1;
			return false;
		}
	case MIDI_PARSE_DATA_1:
		msg->status = ctx->status;
		msg->data[1] = next_byte;

		ctx->parse_state = MIDI_PARSE_STATUS;

		if (ctx->status >= MIDI_STATUS_SYSTEM)
		{
			ctx->status = 0;
		}

		return true;
	case MIDI_PARSE_SYSEX:
		if (ctx->sysex_buf && ctx->sysex_len < ctx->sysex_cap)
		{
			ctx->sysex_buf[ctx->sysex_len] = next_byte;
		}
		ctx->sysex_len++;
		return false;
	case MIDI_PARSE_STATUS: // ignore unexpected data bytes
	default:
		goto error;
	}

error:
	ctx->parse_state = MIDI_PARSE_STATUS;
	return false;
}
