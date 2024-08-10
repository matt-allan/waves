#include "waves.h"
#include "envelope.h"
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

inline void pu1_set_env(uint8_t env_val)
{
	NR12_REG = env_val;
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

inline void pu2_set_env(uint8_t env_val)
{
	NR22_REG = env_val;
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

void tim(void)
{
	uint8_t env_val;

	if ((env_val = envelope_tick(&PU1.envelope))) {
		pu1_set_env(env_val);
		pu1_trigger();
	}

	if ((env_val = envelope_tick(&PU2.envelope))) {
		pu2_set_env(env_val);
		pu2_trigger();
	}
}

void main(void)
{
	CRITICAL
	{
		add_TIM(tim);
	}
	timer_enable();
	apu_enable();
	set_interrupts(VBL_IFLAG | TIM_IFLAG);
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
				// pu1_set_env(
				//     envelope_on(&PU1.envelope, MAX_VOLUME));
				// pu2_set_env(
				//     envelope_on(&PU2.envelope, MAX_VOLUME));
				// pu1_trigger();
				// pu2_trigger();

				wav_set_volume(1);

				wav_set_wave_data(saw_wave_half);
				wav_trigger();
				delay(800);
				wav_set_wave_data(saw_wave);
				wav_trigger();
			}
		} else if (key_released(J_A)) {
			CRITICAL
			{
				// pu1_set_env(envelope_off(&PU1.envelope));
				// pu2_set_env(envelope_off(&PU2.envelope));
				// pu1_trigger();
				// pu2_trigger();

				wav_set_volume(0);
				wav_trigger();
			}
		}

		__asm__("halt");
	}
}
