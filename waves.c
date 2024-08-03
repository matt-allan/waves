#include "waves.h"
#include "envelope.h"
#include <asm/types.h>
#include <gb/gb.h>
#include <gb/hardware.h>
#include <gbdk/console.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

uint8_t last_keys = 0;
uint8_t keys = 0;

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

// TODO: fold this in to the envelope stuff

enum env_sweep_state {
	ENV_SWEEP_NONE = 1 << 0,
	ENV_SWEEP_UP = 1 << 1,
	ENV_SWEEP_DOWN = 1 << 2,
};

uint8_t volume = 0;
uint8_t target_volume = 0;
uint8_t sweep_pace = 0;
uint8_t sweep_counter = 0;
enum env_sweep_state sweep_state;

void tim(void)
{
	switch (sweep_state) {
	  case ENV_SWEEP_UP:
	    if (--sweep_counter == 0) {
	      if (++volume == target_volume) {
	      	// TODO: would move to next stage
	      	sweep_state = ENV_SWEEP_NONE;
	      	sweep_counter = 0;
	      }
	      sweep_counter = sweep_pace;
	      printf("V %d\n", volume);
	    }   
	    break;
	  case ENV_SWEEP_DOWN:
	    if (--sweep_counter == 0) {
	      if (--volume == target_volume) {
	      	// TODO: would move to next stage
	      	sweep_state = ENV_SWEEP_NONE;
	      	sweep_counter = 0;
	      }
	      sweep_counter = sweep_pace; 
	      printf("V %d\n", volume);
	    }   
	  	break;
	  case ENV_SWEEP_NONE:
	  	// ignore
	  	break;
	}
}

inline void pu1_set_env(uint8_t start_volume, enum env_dir dir, uint8_t pace)
{
	NR12_REG = (start_volume << 4) | (dir << 3) | (pace & 0x7);
}

inline void pu1_trigger(uint16_t period)
{
	uint8_t len_en = 0;

	NR13_REG = period & 0xFF;
	NR14_REG = (1 << 7) | (len_en << 6) | (period >> 8);
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

	uint16_t period = 710;

	while (1) {	
		update_keys();
		if (key_ticked(J_A)) {
			printf("ON\n");
			CRITICAL
			{
				sweep_state = ENV_SWEEP_UP;
				sweep_pace = sweep_counter = 7;
				target_volume = MAX_VOLUME;
				pu1_set_env(0, ENV_DIR_UP, sweep_pace);

				pu1_trigger(period);
			}
		} else if (key_released(J_A)) {
			printf("OFF\n");
			CRITICAL
			{
				sweep_state = ENV_SWEEP_DOWN;
				sweep_pace = sweep_counter = 7;
				target_volume = 0;
				pu1_set_env(volume, ENV_DIR_DOWN, sweep_pace);
				pu1_trigger(period);
			}
		}

		__asm__("halt");
	}
}
