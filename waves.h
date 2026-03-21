#ifndef WAVES_WAVES_H
#define WAVES_WAVES_H

#include <stdint.h>
#include <stdbool.h>
#include "envelope.h"


enum sweep_dir {
	SWEEP_DIR_INCR = 0,
	SWEEP_DIR_DECR = 1,
};

enum duty_cycle {
	DUTY_CYCLE_12_5 = 0,
	DUTY_CYCLE_25 = 1,
	DUTY_CYCLE_50 = 2,
	DUTY_CYCLE_75 = 3,
};

struct sweep {
	uint8_t pace;
	enum sweep_dir dir;
	uint8_t step;
};

struct pulse1 {
	uint16_t period;
	enum duty_cycle duty_cycle;
	struct sweep sweep;
	struct envelope envelope;
};

struct pulse2 {
	uint16_t period;
	enum duty_cycle duty_cycle;
	struct envelope envelope;
};

struct wave {
	uint16_t period;
	/** The length of the envelope if fixed */
	uint8_t length;
	/** The wave amplitude (0-3) */
	uint8_t volume;
	/** The wave pattern loaded into RAM */
	uint8_t wave[16];
};

#endif // WAVES_WAVES_H