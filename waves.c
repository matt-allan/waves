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
	return (env->start_volume << 4) | (env->direction << 3) | (env->sweep_pace & 0x7);
}

void pu1_set_sweep(uint8_t pace, enum sweep_dir dir, uint8_t step)
{
	struct sweep *sweep = &PU1.sweep;
	sweep->pace = pace;
	sweep->dir = dir;
	sweep->step = step;

	NR10_REG = (pace << 4) | (dir << 3) | step;
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

static void note_on(enum instrument instr, uint16_t period)
{
	switch (instr) {
	case INSTR_PU1:
		PU1.period = period;
		envelope_on(&PU1.envelope, MAX_VOLUME);
		pu1_update_env();
		pu1_trigger();
		break;
	case INSTR_PU2:
		PU2.period = period;
		envelope_on(&PU2.envelope, MAX_VOLUME);
		pu2_update_env();
		pu2_trigger();
		break;
	case INSTR_WAV:
		WAV.period = period;
		wav_trigger();
		break;
	case INSTR_NOISE:
		break;
	}
}

static void note_off(enum instrument instr)
{
	switch (instr) {
	case INSTR_PU1:
		envelope_off(&PU1.envelope);
		pu1_update_env();
		pu1_trigger();
		break;
	case INSTR_PU2:
		envelope_off(&PU2.envelope);
		pu2_update_env();
		pu2_trigger();
		break;
	case INSTR_WAV:
		wav_set_volume(0);
		break;
	case INSTR_NOISE:
		break;
	}
}

static void set_param(enum instrument instr, uint8_t param_id, uint8_t value)
{
	if (instr == INSTR_WAV && param_id >= MCU_PARAM_WAVE_0 &&
	    param_id < MCU_PARAM_WAVE_0 + 16) {
		uint8_t i = param_id - MCU_PARAM_WAVE_0;
		WAV.wave[i] = value;
		NR30_REG = 0x00;
		((unsigned char *)0xFF30)[i] = value;
		NR30_REG = 0x80;
		return;
	}

	switch (param_id) {
	case MCU_PARAM_ATTACK:
		if (instr == INSTR_PU1)
			PU1.envelope.attack = value;
		else if (instr == INSTR_PU2)
			PU2.envelope.attack = value;
		break;
	case MCU_PARAM_DECAY:
		if (instr == INSTR_PU1)
			PU1.envelope.decay = value;
		else if (instr == INSTR_PU2)
			PU2.envelope.decay = value;
		break;
	case MCU_PARAM_SUSTAIN:
		if (instr == INSTR_PU1)
			PU1.envelope.sustain = value;
		else if (instr == INSTR_PU2)
			PU2.envelope.sustain = value;
		break;
	case MCU_PARAM_RELEASE:
		if (instr == INSTR_PU1)
			PU1.envelope.release = value;
		else if (instr == INSTR_PU2)
			PU2.envelope.release = value;
		break;
	case MCU_PARAM_DUTY_CYCLE:
		if (instr == INSTR_PU1)
			pu1_set_duty_cycle((enum duty_cycle)value);
		else if (instr == INSTR_PU2)
			pu2_set_duty_cycle((enum duty_cycle)value);
		break;
	case MCU_PARAM_SWEEP_PACE:
		if (instr == INSTR_PU1) {
			PU1.sweep.pace = value;
			NR10_REG = (PU1.sweep.pace << 4) |
				   (PU1.sweep.dir << 3) | PU1.sweep.step;
		}
		break;
	case MCU_PARAM_SWEEP_DIR:
		if (instr == INSTR_PU1) {
			PU1.sweep.dir = (enum sweep_dir)value;
			NR10_REG = (PU1.sweep.pace << 4) |
				   (PU1.sweep.dir << 3) | PU1.sweep.step;
		}
		break;
	case MCU_PARAM_SWEEP_STEP:
		if (instr == INSTR_PU1) {
			PU1.sweep.step = value;
			NR10_REG = (PU1.sweep.pace << 4) |
				   (PU1.sweep.dir << 3) | PU1.sweep.step;
		}
		break;
	case MCU_PARAM_VOLUME:
		if (instr == INSTR_WAV)
			wav_set_volume(value);
		break;
	}
}

void serial_isr(void)
{
	uint8_t byte = SB_REG;

	switch (rx.state) {
	case RX_IDLE:
		rx.hdr = byte;
		switch (mcu_hdr_cmd(byte)) {
		case MCU_NOTE_ON:
			rx.state = RX_NOTE_ON;
			break;
		case MCU_NOTE_OFF:
			note_off(mcu_hdr_instr(byte));
			break;
		case MCU_SET_PARAM:
			rx.state = RX_PARAM_ID;
			break;
		}
		break;
	case RX_NOTE_ON:
		note_on(mcu_hdr_instr(rx.hdr),
			((uint16_t)mcu_hdr_data(rx.hdr) << 8) | byte);
		rx.state = RX_IDLE;
		break;
	case RX_PARAM_ID:
		rx.param_id = byte;
		rx.state = RX_PARAM_VAL;
		break;
	case RX_PARAM_VAL:
		set_param(mcu_hdr_instr(rx.hdr), rx.param_id, byte);
		rx.state = RX_IDLE;
		break;
	}

	SB_REG = 0xFF;
	SC_REG = 0x81; /* re-arm; use 0x80 for external MCU clock */
}

void tim(void)
{
	uint8_t env_val;

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
