#ifndef WAVES_WAVES_H
#define WAVES_WAVES_H

#include <stdint.h>
#include <stdbool.h>
#include "envelope.h"

/**
 * Covers notes from C3 to B8.
 * 
 * @see http://www.devrs.com/gb/files/sndtab.html
 */
const uint16_t frequencies[] = {
  44, 156, 262, 363, 457, 547, 631, 710, 786, 854, 923, 986,
  1046, 1102, 1155, 1205, 1253, 1297, 1339, 1379, 1417, 1452, 1486, 1517,
  1546, 1575, 1602, 1627, 1650, 1673, 1694, 1714, 1732, 1750, 1767, 1783,
  1798, 1812, 1825, 1837, 1849, 1860, 1871, 1881, 1890, 1899, 1907, 1915,
  1923, 1930, 1936, 1943, 1949, 1954, 1959, 1964, 1969, 1974, 1978, 1982,
  1985, 1988, 1992, 1995, 1998, 2001, 2004, 2006, 2009, 2011, 2013, 2015
};

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

#endif // WAVES_WAVES_H