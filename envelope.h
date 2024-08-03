#ifndef WAVES_ENVELOPE_H
#define WAVES_ENVELOPE_H

#include <stdbool.h>
#include <stdint.h>

/**
 * The maximum possible register value for an envelope's volume.
 */
static const uint8_t MAX_VOLUME = 15;

/**
 * The register value for an envelope's direction.
 */
enum env_dir
{
	ENV_DIR_DOWN = 0,
	ENV_DIR_UP = 1,
};

/**
 * The current stage of the volume envelope.
 */
enum env_stage
{
	ENV_STAGE_ATTACK = 1 << 0,
	ENV_STAGE_DECAY = 1 << 1,
	ENV_STAGE_SUSTAIN = 1 << 2,
	ENV_STAGE_RELEASE = 1 << 3,
};

/**
 * The # of `env_stage` constants.
 */
static const uint8_t NUM_ENV_STAGES = 4;

/**
 * An ADSR volume envelope for a pulse or noise channel.
 * 
 * The envelope registers can only count up or down and cannot be stopped at a
 * particular volume. To create a full ADSR envelope the registers must be
 * written 4 times in succession at the exact time.
 **/
struct envelope
{
	/** The current volume. If 0 the envelope is off */
	uint8_t volume;
	/** Countdown until the next stage (0 - (15*7)) */
	uint8_t counter;
	/** The current stage */
	enum env_stage stage;
	/** The current direction */
	enum env_dir direction;

	/** Attack length sweep pace (1-7) */
	uint8_t attack;
	/** Decay sweep pace (1-7) */
	uint8_t decay;
	/** Sustain volume (1-15) */
	uint8_t sustain;
	/** Release pace (1-7) */
	uint8_t release;
};

/**
 * Start the attack stage.
 */
uint8_t envelope_attack(struct envelope *env);

/**
 * Start the decay stage.
 */
uint8_t envelope_decay(struct envelope *env);

/**
 * Start the sustain stage.
 */
uint8_t envelope_sustain(struct envelope *env);

/**
 * Start the release stage.
 */
uint8_t envelope_release(struct envelope *env);

/**
 * Immediately stop the envelope without waiting for release.
 */
uint8_t envelope_stop(struct envelope *env);

/**
 * Advance the envelope one tick.
 * 
 * The envelope should be advanced at 64 Hz to match the DIV-APU's envelope
 * sweep.
 * 
 * Returns the next register value to set or 0 to keep the current value.
 */
uint8_t envelope_tick(struct envelope *env);

#endif // WAVES_ENVELOPE_H