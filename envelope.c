#include "envelope.h"
#include <stdint.h>

inline void env_reset_length_timer(struct envelope *env)
{
	if (env->length) {
		env->length_timer = (64 - env->length) * 4;
	}
}

void envelope_attack(struct envelope *env, uint8_t volume)
{
	uint8_t attack = env->attack;

	env->stage = ENV_STAGE_ATTACK;
	env->direction = ENV_DIR_UP;
	env->sweep_pace = env->sweep_timer = attack;
	env->start_volume = attack ? 0 : volume;
	env->target_volume = volume;
}

void envelope_decay(struct envelope *env)
{
	uint8_t decay = env->decay;

	env->stage = ENV_STAGE_DECAY;
	env->direction = ENV_DIR_DOWN;
	env->sweep_pace = env->sweep_timer = decay;
	env->start_volume = env->volume;
	env->target_volume = env->volume - env->sustain;
}

void envelope_sustain(struct envelope *env)
{
	env->stage = ENV_STAGE_SUSTAIN;
	env->direction = ENV_DIR_UP; // needs to be up to stay on
	env->sweep_pace = env->sweep_timer = 0;
	env->start_volume = env->volume;
	// target_volume is already set
}

void envelope_release(struct envelope *env)
{
	uint8_t release = env->release;

	env->stage = ENV_STAGE_RELEASE;
	env->direction = ENV_DIR_DOWN;
	env->sweep_pace = env->sweep_timer = release;
	env->start_volume = env->volume;
	env->target_volume = 0;
}

void envelope_end(struct envelope *env)
{
	env->volume = env->start_volume = env->target_volume = 0;
	env->direction = ENV_DIR_UP; // needs to be up to keep DAC on
	env->sweep_timer = 0;
}

void envelope_on(struct envelope *env, uint8_t volume)
{
	env_reset_length_timer(env);

	envelope_attack(env, volume);
}

void envelope_off(struct envelope *env)
{
	if (env->stage != ENV_STAGE_RELEASE) {
		envelope_release(env);
	}
}

void envelope_kill(struct envelope *env)
{
	envelope_end(env);
}

bool envelope_next(struct envelope *env)
{
	switch (env->stage) {
	case ENV_STAGE_ATTACK:
		if (env->decay && env->sustain) {
			envelope_decay(env);
			return true;
		} 
		// fallthrough
	case ENV_STAGE_DECAY:
		if (env->sustain) {
			envelope_sustain(env);
			return true;
		}
		// fallthrough
	case ENV_STAGE_SUSTAIN:
		if (env->release) {
			envelope_release(env);
			return true;
		}
		// fallthrough
	case ENV_STAGE_RELEASE:
		envelope_end(env);
		return false;
	}
}

bool envelope_tick(struct envelope *env)
{
	if (env->length_timer && --env->length_timer == 0) {
		envelope_end(env); 
		return false;
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
	return false;
}
