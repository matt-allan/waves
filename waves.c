#include "waves.h"
#include "envelope.h"
#include <asm/types.h>
#include <gb/gb.h>
#include <gb/hardware.h>
// #include <gbdk/console.h>
#include <stdbool.h>
#include <stdint.h>
// #include <stdio.h>

uint8_t last_keys = 0;
uint8_t keys = 0;

struct pulse1 PU1 = {
	.envelope = {0}
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
	NR51_REG = 0x11; // enable L&R outputs for all channels
	NR50_REG = 0x77; // max volume L&R
}

inline void pu1_set_sweep(uint8_t pace, enum sweep_dir dir, uint8_t step)
{
	struct sweep* sweep = &PU1.sweep;
	sweep->pace = pace;
	sweep->dir = dir;
	sweep->step = step;

	NR10_REG =  (pace << 4) | (dir << 3) | step;
}


inline void pu1_set_duty_cycle(enum duty_cycle duty)
{
	PU1.duty_cycle = duty;
	NR11_REG = (duty << 6) | (NR11_REG & 0x1F);
}

inline void pu1_set_length(uint8_t len)
{
	PU1.envelope.length = len;
	NR11_REG = len | (NR11_REG & 0xC0);
}

inline void pu1_set_env(uint8_t env_val)
{
	NR12_REG = env_val;
}

inline void pu1_trigger()
{
	uint8_t len_en = PU1.envelope.length != 0;
	uint16_t period = PU1.period;

	NR13_REG = period & 0xFF;
	NR14_REG = (1 << 7) | (len_en << 6) | (period >> 8);
}

void tim(void)
{
	uint8_t env_val = envelope_tick(&PU1.envelope);
	if (env_val != 0) {
		pu1_set_env(env_val);
		pu1_trigger();
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

	PU1.period = 710;
	PU1.envelope.attack = 7;
	PU1.envelope.decay = 7;
	PU1.envelope.sustain = 2;
	PU1.envelope.release = 7;

	while (1) {
		update_keys();
		if (key_ticked(J_A)) {
			CRITICAL
			{
				pu1_set_env(envelope_on(&PU1.envelope, MAX_VOLUME));
				pu1_trigger();
			}
		} else if (key_released(J_A)) {
			CRITICAL
			{
				pu1_set_env(envelope_off(&PU1.envelope));
				pu1_trigger();
			}
		}

		__asm__("halt");
	}
}
