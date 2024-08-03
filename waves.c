#include "waves.h"
#include "envelope.h"
#include <asm/types.h>
#include <gb/gb.h>
#include <gb/hardware.h>
#include <gbdk/console.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

uint8_t PREV_KEYS = 0;
uint8_t KEYS = 0;

struct pulse1 PU1 = {
    0, 0, DUTY_CYCLE_12_5, {0, 0, 0}, {0, 0, ENV_STAGE_ATTACK, ENV_DIR_UP, 0, 0, 0, 0}};

inline void update_keys(void)
{
	PREV_KEYS = KEYS;
	KEYS = joypad();
}

void tim(void)
{
	uint8_t reg = envelope_tick(&PU1.envelope);
	if (reg != 0) {
		printf(">\n");
		NR12_REG = reg;
	}
}

inline bool key_pressed(uint8_t k)
{
	return KEYS & (k);
}

inline bool key_ticked(uint8_t k)
{
	return ((KEYS & (k)) && !(PREV_KEYS & (k)));
}

inline void apu_enable(void)
{
	NR52_REG = 0x80; // power on the APU
	NR51_REG = 0x11; // enable L&R outputs for all channels
	NR50_REG = 0x77; // max volume L&R
}

// TODO: replace most of these with more specific fns

// inline void pu1_sweep_set(uint8_t pace, enum sweep_dir dir, uint8_t step)
// {
// 	assert(pace <= 7);
// 	assert(step <= 7);
// 	NR10_REG =  (pace << 4) | (dir << 3) | step;
// }

// inline void pu1_sweep_pace_set(uint8_t pace)
// {
// 	assert(pace <= 7);
// 	NR10_REG =  (pace << 4) | (NR10_REG & 0xF);
// }

// inline void pu1_sweep_dir_set(enum sweep_dir dir)
// {
// 	NR10_REG =  (dir << 3) | (NR10_REG & 0xF7);
// }

// inline void pu1_sweep_step_set(uint8_t step)
// {
// 	assert(step <= 7);
// 	NR10_REG =  step | (NR10_REG & 0xF8);
// }

// inline void pu1_duty_cycle_set(enum duty_cycle duty)
// {
// 	NR11_REG = (duty << 6) | (NR11_REG & 0x1F);
// }

// inline void pu1_length_counter_set(uint8_t counter)
// {
// 	assert(counter <= 63);
// 	pu1_length_enabled = counter > 0;
// 	NR11_REG = counter | (NR11_REG & 0xC0);
// }

// // TODO: this is envelope initial volume, not overall volume
// inline void pu1_volume_set(uint8_t volume)
// {
// 	assert(volume <= 15);
// 	NR12_REG = (volume << 4) | (NR12_REG & 0xF);
// }

// inline void pu1_env_dir_set(enum env_dir dir)
// {
// 	NR12_REG = (dir << 3) | (NR12_REG & 0xF7);
// }

// inline void pu1_env_sweep_pace_set(uint8_t pace)
// {
// 	assert(pace <= 7);
// 	NR12_REG = pace | (NR12_REG & 0xF8);
// }

// inline void pu1_play(uint16_t period)
// {
// 	assert(period <= 2047);
// 	NR13_REG = period & 0xFF;
// 	NR14_REG = (1 << 7) | (pu1_length_enabled << 6) | (period >> 8);
// }

// inline void pu1_stop(void)
// {
// 	NR12_REG = 0x08;
// 	NR13_REG = 0x00;
// 	NR14_REG = 0x80;
// }

inline void pu1_trigger(void)
{
	uint16_t period = PU1.period;
	uint8_t len_en = PU1.length != 0;

	NR13_REG = period & 0xFF;
	NR14_REG = (1 << 7) | (len_en << 6) | (period >> 8);
}

// inline void pu1_set_env(uint8_t start_volume, enum env_dir dir, uint8_t pace)
// {
// 	NR12_REG = (start_volume << 4) | (dir << 3) | (pace & 0x7);
// }

/**
 * Turn on the channel, starting the attack phase of the volume envelope.
 */
void pu1_on(uint16_t period)
{

	CRITICAL
	{
		PU1.period = period;
		NR12_REG = envelope_attack(&PU1.envelope);
		pu1_trigger();
	}
}

/**
 * Turn off the channel, immediately advancing to the release phase of the
 * volume envelope.
 */
void pu1_off(void)
{
	CRITICAL
	{
		NR12_REG = envelope_release(&PU1.envelope);
		pu1_trigger();
	}
}

void main(void)
{
	CRITICAL
	{
		add_TIM(tim);
	}

	TAC_REG = 0x04U; // 4096 Hz, every 256 M cycles
	TMA_REG = 0xC0;	 // prescale by 64 to match DIV-APU env sweep

	apu_enable();

	set_interrupts(VBL_IFLAG | TIM_IFLAG);
	enable_interrupts();

	// Set some defaults for testing
	PU1.envelope.attack = 7;
	PU1.envelope.decay = 7;
	PU1.envelope.sustain = 6;
	PU1.envelope.release = 7;

	bool note_on = false;

	while (1) {
		update_keys();
		if (key_ticked(J_A) && !note_on) {
			note_on = true;
			printf("P\n");
			pu1_on(44);
		} else if (!key_pressed(J_A) && note_on) {
			note_on = false;
			printf("S\n");
			pu1_off();
		}

		__asm__("halt");
	}
}
