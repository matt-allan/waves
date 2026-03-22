#include "waves.h"
#include "envelope.h"
#include "protocol.h"
#include <asm/types.h>
#include <assert.h>
#include <gb/gb.h>
#include <gb/hardware.h>
// #include <gbdk/console.h>
#include <stdbool.h>
#include <stdint.h>
// #include <stdio.h>

uint8_t last_keys = 0;
uint8_t keys = 0;

struct pulse1 PU1 = {.envelope = {0}};

struct pulse2 PU2 = {.envelope = {0}};

static struct rx_buf rx;

struct wave WAV = {
    .wave = {0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00,
	     0xFF, 0x00, 0xFF, 0x00, 0xFF},
};

inline void update_keys(void)
{
	last_keys = keys;
	keys = joypad();
}

inline bool key_pressed(uint8_t k)
{
	return keys & (k);
}

inline bool key_ticked(uint8_t k)
{
	return (keys & (k)) && !(last_keys & (k));
}

inline bool key_released(uint8_t k)
{
	return !(keys & (k)) && (last_keys & (k));
}

inline void timer_enable(void)
{
	TAC_REG = 0x04U; // 4096 Hz, every 256 M cycles
	TMA_REG = 0xC0;	 // prescale by 64 to match DIV-APU env sweep
}

inline void apu_enable(void)
{
	NR52_REG = 0x80; // power on the APU
	NR51_REG = 0xFF; // enable L&R outputs for all channels
	NR50_REG = 0x77; // max volume L&R
}


inline uint8_t env_reg_val(struct envelope *env)
{
	return (env->volume << 4) | (env->direction << 3) | (env->sweep_pace & 0x7);
}

void pu1_set_sweep(uint8_t nr10)
{
	PU1.nr10 = nr10;
	NR10_REG = nr10;
}

void pu1_set_duty_cycle(enum duty_cycle duty)
{
	PU1.duty_cycle = duty;
	NR11_REG = (duty << 6) | (NR11_REG & 0x1F);
}

void pu1_set_length(uint8_t len)
{
	PU1.envelope.length = len;
	NR11_REG = len | (NR11_REG & 0xC0);
}

inline void pu1_update_env(void)
{
	NR12_REG = env_reg_val(&PU1.envelope);
}

void pu1_trigger(void)
{
	uint8_t len_en = PU1.envelope.length != 0;
	uint16_t period = PU1.period;

	NR13_REG = period & 0xFF;
	NR14_REG = (1 << 7) | (len_en << 6) | (period >> 8);
}

void pu2_set_duty_cycle(enum duty_cycle duty)
{
	PU2.duty_cycle = duty;
	NR21_REG = (duty << 6) | (NR11_REG & 0x1F);
}

void pu2_set_length(uint8_t len)
{
	PU2.envelope.length = len;
	NR21_REG = len | (NR21_REG & 0xC0);
}

inline void pu2_update_env(void)
{
	NR22_REG = env_reg_val(&PU2.envelope);
}

void pu2_trigger(void)
{
	uint8_t len_en = PU2.envelope.length != 0;
	uint16_t period = PU2.period;

	NR23_REG = period & 0xFF;
	NR24_REG = (1 << 7) | (len_en << 6) | (period >> 8);
}

void wav_set_length(uint8_t len)
{
	WAV.length = len;
	NR31_REG = len;
}

void wav_set_volume(uint8_t volume)
{
	WAV.volume = volume;
	NR32_REG = (volume << 5);
}

void wav_set_wave_data(uint8_t wave_data[16])
{	
	NR30_REG = 0x00;
	unsigned char *wave_ram = (unsigned char *)0xFF30;
	for (uint8_t i = 0; i < 16; i++) {
		*wave_ram = wave_data[i];
		WAV.wave[i] = wave_data[i];
		wave_ram++;
	}
	NR30_REG = 0x80;
}

void wav_trigger(void)
{
	uint8_t len_en = WAV.length != 0;
	uint16_t period = WAV.period;

	NR33_REG = period & 0xFF;
	NR34_REG = (1 << 7) | (len_en << 6) | (period >> 8);
}

void serial_isr(void)
{
	uint8_t byte = SB_REG;

	switch (rx.state) {
	case RX_IDLE:
		rx.hdr = byte;
		switch (byte) {
		/* NOTE_ON — all instruments need 2-byte period payload */
		case PROTO_HDR(INSTR_PU1, MCU_NOTE_ON):
		case PROTO_HDR(INSTR_PU2, MCU_NOTE_ON):
		case PROTO_HDR(INSTR_WAV, MCU_NOTE_ON):
		case PROTO_HDR(INSTR_NOISE, MCU_NOTE_ON):
			rx.state = RX_NOTE_HI;
			break;
		/* NOTE_OFF — immediate, per-instrument */
		case PROTO_HDR(INSTR_PU1, MCU_NOTE_OFF):
			envelope_off(&PU1.envelope);
			pu1_update_env();
			pu1_trigger();
			break;
		case PROTO_HDR(INSTR_PU2, MCU_NOTE_OFF):
			envelope_off(&PU2.envelope);
			pu2_update_env();
			pu2_trigger();
			break;
		case PROTO_HDR(INSTR_WAV, MCU_NOTE_OFF):
			wav_set_volume(0);
			break;
		/* WAV_SET_WAVE — 16-byte payload */
		case PROTO_HDR(INSTR_WAV, WAV_SET_WAVE):
			rx.wave_idx = 0;
			NR30_REG = 0x00;
			rx.state = RX_WAVE;
			break;
		/*
		 * All other param commands carry one value byte.
		 * Reserved slots and idle-line 0xFF (cmd=31) fall
		 * through to default and are safely ignored.
		 */
		default: {
			uint8_t cmd = proto_cmd(byte);
			if (cmd >= CMD_CHAN_VOLUME && cmd <= PU1_SWEEP)
				rx.state = RX_VAL;
			break;
		}
		}
		break;
	case RX_NOTE_HI:
		rx.period_hi = byte;
		rx.state = RX_NOTE_LO;
		break;
	case RX_NOTE_LO: {
		uint16_t period =
			((uint16_t)(rx.period_hi & 0x07) << 8) | byte;
		switch (rx.hdr) {
		case PROTO_HDR(INSTR_PU1, MCU_NOTE_ON):
			PU1.period = period;
			envelope_on(&PU1.envelope, MAX_VOLUME);
			pu1_update_env();
			pu1_trigger();
			break;
		case PROTO_HDR(INSTR_PU2, MCU_NOTE_ON):
			PU2.period = period;
			envelope_on(&PU2.envelope, MAX_VOLUME);
			pu2_update_env();
			pu2_trigger();
			break;
		case PROTO_HDR(INSTR_WAV, MCU_NOTE_ON):
			WAV.period = period;
			wav_trigger();
			break;
		}
		rx.state = RX_IDLE;
		break;
	}
	case RX_VAL:
		switch (rx.hdr) {
		case PROTO_HDR(INSTR_PU1, CMD_ATTACK):
			PU1.envelope.attack = byte;
			break;
		case PROTO_HDR(INSTR_PU1, CMD_DECAY):
			PU1.envelope.decay = byte;
			break;
		case PROTO_HDR(INSTR_PU1, CMD_SUSTAIN):
			PU1.envelope.sustain = byte;
			break;
		case PROTO_HDR(INSTR_PU1, CMD_RELEASE):
			PU1.envelope.release = byte;
			break;
		case PROTO_HDR(INSTR_PU1, PU1_DUTY_CYCLE):
			pu1_set_duty_cycle((enum duty_cycle)byte);
			break;
		case PROTO_HDR(INSTR_PU1, PU1_SWEEP):
			PU1.nr10 = byte;
			NR10_REG = byte;
			break;
		case PROTO_HDR(INSTR_PU2, CMD_ATTACK):
			PU2.envelope.attack = byte;
			break;
		case PROTO_HDR(INSTR_PU2, CMD_DECAY):
			PU2.envelope.decay = byte;
			break;
		case PROTO_HDR(INSTR_PU2, CMD_SUSTAIN):
			PU2.envelope.sustain = byte;
			break;
		case PROTO_HDR(INSTR_PU2, CMD_RELEASE):
			PU2.envelope.release = byte;
			break;
		case PROTO_HDR(INSTR_PU2, PU2_DUTY_CYCLE):
			pu2_set_duty_cycle((enum duty_cycle)byte);
			break;
		case PROTO_HDR(INSTR_WAV, CMD_VOLUME):
			wav_set_volume(byte);
			break;
		}
		rx.state = RX_IDLE;
		break;
	case RX_WAVE:
		WAV.wave[rx.wave_idx] = byte;
		((unsigned char *)0xFF30)[rx.wave_idx] = byte;
		if (++rx.wave_idx == 16) {
			NR30_REG = 0x80;
			rx.state = RX_IDLE;
		}
		break;
	}

	SB_REG = 0xFF;
	SC_REG = 0x81; /* re-arm; use 0x80 for external MCU clock */
}

void tim(void)
{
	if (envelope_tick(&PU1.envelope)) {
		pu1_update_env();
		pu1_trigger();
	}

	if (envelope_tick(&PU2.envelope)) {
		pu2_update_env();
		pu2_trigger();
	}
}

void main(void)
{
	CRITICAL
	{
		add_TIM(tim);
		add_SIO(serial_isr);
	}
	timer_enable();
	apu_enable();
	SB_REG = 0xFF;
	SC_REG = 0x81; /* start first transfer; use 0x80 for external MCU clock */
	set_interrupts(VBL_IFLAG | TIM_IFLAG | SIO_IFLAG);
	enable_interrupts();

	PU1.period = 1046;
	PU1.envelope.attack = 7;
	PU1.envelope.decay = 7;
	PU1.envelope.sustain = 2;
	PU1.envelope.release = 7;

	PU2.period = 1379;
	PU2.envelope.attack = 7;
	PU2.envelope.decay = 7;
	PU2.envelope.sustain = 2;
	PU2.envelope.release = 7;

	uint8_t saw_wave_half[16] = {0x77, 0x66, 0x55, 0x44, 0x33, 0x22, 0x11, 0x00, 0x77, 0x66, 0x55, 0x44, 0x33, 0x22, 0x11, 0x00};

	uint8_t saw_wave[16] = {0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54, 0x32, 0x10,
				0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54, 0x32, 0x10};

	WAV.period = 1379;
	wav_set_wave_data(saw_wave);

	while (1) {
		update_keys();
		if (key_ticked(J_A)) {
			CRITICAL
			{
				envelope_on(&PU1.envelope, MAX_VOLUME);
				pu1_update_env();
				// envelope_on(&PU2.envelope, MAX_VOLUME);
				// pu2_set_env();
				pu1_trigger();
				// pu2_trigger();

				// wav_set_volume(1);

				// wav_set_wave_data(saw_wave_half);
				// wav_trigger();
				// delay(800);
				// wav_set_wave_data(saw_wave);
				// wav_trigger();
			}
		} else if (key_released(J_A)) {
			CRITICAL
			{
				envelope_off(&PU1.envelope);
				pu1_update_env();
				// envelope_off(&PU2.envelope);
				// pu2_set_env();
				pu1_trigger();
				// pu2_trigger();

				// wav_set_volume(0);
				// wav_trigger();
			}
		}

		__asm__("halt");
	}
}
