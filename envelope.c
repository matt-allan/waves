#include "envelope.h"

inline uint8_t env_reg_val(uint8_t start_volume, enum env_dir dir, uint8_t pace)
{
	return (start_volume << 4) | (dir << 3) | (pace & 0x7);
}

uint8_t envelope_attack(struct envelope *env)
{
	env->volume = 0;
	env->stage = ENV_STAGE_ATTACK;
	env->direction = ENV_DIR_UP;
	// TODO is this actually based on the note on velocity?
	env->counter = MAX_VOLUME * env->attack;

	return env_reg_val(0, ENV_DIR_UP, env->attack);
}

uint8_t envelope_decay(struct envelope *env)
{
	env->stage = ENV_STAGE_DECAY;
	env->direction = ENV_DIR_DOWN;
	env->counter = MAX_VOLUME * env->decay;

	return env_reg_val(MAX_VOLUME, ENV_DIR_DOWN, env->decay);
}

uint8_t envelope_sustain(struct envelope *env)
{
	env->stage = ENV_STAGE_SUSTAIN;
	env->direction = ENV_DIR_UP;
	env->counter = 0;

	return env_reg_val(env->sustain, ENV_DIR_UP, 0);
}

uint8_t envelope_release(struct envelope *env)
{
	env->stage = ENV_STAGE_RELEASE;
	env->direction = ENV_DIR_DOWN;
	env->counter = env->volume * env->release;

	return env_reg_val(env->volume, ENV_DIR_DOWN, env->release);
}

uint8_t envelope_stop(struct envelope *env)
{
	// Reset to the initial state
	env->stage = ENV_STAGE_ATTACK;
	env->direction = ENV_DIR_UP;
	env->counter = 0;
	env->volume = 0;

	return 0x08;
}

uint8_t envelope_tick(struct envelope *env)
{
	if (env->counter > 0 && --env->counter == 0) {
		switch (env->stage) {
		case ENV_STAGE_ATTACK:		
			// TODO: decay is not stopping (counter issue?)
			return envelope_decay(env);
		case ENV_STAGE_DECAY:
			return envelope_sustain(env);
		case ENV_STAGE_SUSTAIN:
			return envelope_release(env);
		case ENV_STAGE_RELEASE:
			return envelope_stop(env);
		}
	}

	return 0;
}
