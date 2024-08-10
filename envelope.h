#ifndef WAVES_ENVELOPE_H
#define WAVES_ENVELOPE_H

#include <stdbool.h>
#include <stdint.h>

/**
 * The maximum possible register value for an envelope's volume.
 */
static const uint8_t MAX_VOLUME = 15;

enum env_dir {
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
 * An ADSR volume envelope for a channel.
 **/
struct envelope
{	
	/** Attack length sweep pace (1-7) */
	uint8_t attack;
	/** Decay sweep pace (1-7) */
	uint8_t decay;
	/** Sustain volume difference from attack volume */
	uint8_t sustain;
	/** Release pace (1-7) */
	uint8_t release;
	/** The current volume. If 0 the envelope is off */
	uint8_t volume;
	/** The length of the envelope if fixed (0-63) */
	uint8_t length;
	/** Counts down until stop */
	uint8_t length_timer;
	/** The volume we are sweeping from. */
	uint8_t start_volume;
	/** The volume we are sweeping towards. */
	uint8_t target_volume;
	/** The current sweep pace. */
	uint8_t sweep_pace;	
	/** Counts down until the next volume change **/
	uint8_t sweep_timer;
	/** The current envelope stage */
	enum env_stage stage;
	/** The current sweep direction */
	enum env_dir direction;
};

/**
 * Turn on the envelope, starting the attack stage.
 */
void envelope_on(struct envelope *env, uint8_t volume);

/**
 * Turn off the envelope, moving to the release phase.
 */
void envelope_off(struct envelope *env);

/**
 * Immediately stop the envelope.
 */
void envelope_kill(struct envelope *env);

/**
 * Advance the envelope one tick.
 * 
 * The envelope should be advanced at 64 Hz to match the DIV-APU's envelope
 * sweep.
 * 
 * Returns true if the envelope stage has changed.
 */
bool envelope_tick(struct envelope *env);

#endif // WAVES_ENVELOPE_H