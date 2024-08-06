#include "envelope.h"
#include <stdint.h>

inline uint8_t env_reg_val(uint8_t start_volume, enum env_dir dir, uint8_t pace)
{
	return (start_volume << 4) | (dir << 3) | (pace & 0x7);
}

inline void env_reset_length_timer(struct envelope *env)
{
	if (env->length) {
		env->length_timer = (64 - env->length) * 4;
	}
}

inline uint8_t envelope_attack(struct envelope *env, uint8_t volume)
{
	uint8_t attack = env->attack;

	env->stage = ENV_STAGE_ATTACK;
	env->direction = ENV_DIR_UP;
	env->sweep_pace = env->sweep_timer = attack;
	env->target_volume = volume;

	if (!attack) {
		return env_reg_val(volume, ENV_DIR_UP, attack);
	}

	return env_reg_val(0, ENV_DIR_UP, attack);
}

inline uint8_t envelope_decay(struct envelope *env)
{
	uint8_t decay = env->decay;

	env->stage = ENV_STAGE_DECAY;
	env->direction = ENV_DIR_DOWN;
	env->sweep_pace = env->sweep_timer = decay;
	env->target_volume = env->volume - env->sustain;

	return env_reg_val(env->volume, ENV_DIR_DOWN, decay);
}

inline uint8_t envelope_sustain(struct envelope *env)
{
	env->stage = ENV_STAGE_SUSTAIN;
	env->direction = ENV_DIR_UP; // needs to be up to stay on
	env->sweep_pace = env->sweep_timer = 0;
	// target_volume is already set

	return env_reg_val(env->volume, ENV_DIR_UP, 0);
}

inline uint8_t envelope_release(struct envelope *env)
{
	uint8_t release = env->release;

	env->stage = ENV_STAGE_RELEASE;
	env->direction = ENV_DIR_DOWN;
	env->sweep_pace = env->sweep_timer = release;
	env->target_volume = 0;

	return env_reg_val(env->volume, ENV_DIR_DOWN, release);
}

inline uint8_t envelope_end(struct envelope *env)
{
	env->volume = 0;
	env->sweep_timer = 0;

	return 0x08;
}

uint8_t envelope_on(struct envelope *env, uint8_t volume)
{
	env_reset_length_timer(env);

	return envelope_attack(env, volume);
}

uint8_t envelope_off(struct envelope *env)
{
	if (env->stage == ENV_STAGE_RELEASE) {
		return 0;
	} else {
		return envelope_release(env);
	}
}

uint8_t envelope_kill(struct envelope *env)
{
	return envelope_end(env);
}

uint8_t envelope_next(struct envelope *env)
{
	switch (env->stage) {
	case ENV_STAGE_ATTACK:
		if (env->decay && env->sustain) {
			return envelope_decay(env);
		} 
		// fallthrough
	case ENV_STAGE_DECAY:
		if (env->sustain) {
			return envelope_sustain(env);
		}
		// fallthrough
	case ENV_STAGE_SUSTAIN:
		if (env->release) {
			return envelope_release(env);
		}
		// fallthrough
	case ENV_STAGE_RELEASE:
		return envelope_end(env);
	}
}

uint8_t envelope_tick(struct envelope *env)
{
	if (env->length_timer && --env->length_timer == 0) {
		envelope_kill(env);  // ignore register value; HW will kill it
		return 0;
	}

	if (env->sweep_timer != 0) {
		if (--env->sweep_timer == 0) {
			if (env->direction == ENV_DIR_UP) {
				env->volume++;
			} else {
				env->volume--;
			}

			if (env->volume == env->target_volume) {
				return envelope_next(env);
			} else {
				env->sweep_timer = env->sweep_pace;
			}
		}
	}
	return 0;
}
