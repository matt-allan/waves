GBDK_HOME ?= tools/gbdk/

CC       := $(GBDK_HOME)bin/lcc
ROMUSAGE := $(GBDK_HOME)bin/romusage
CFLAGS   := -Wa-l -Wl-m -Wl-j -msm83:gb -Iwaves/src

ifdef DEBUG
	CFLAGS += -debug -v
endif

GAME := waves

SAMEBOY_ROOT := vendor/SameBoy
SAMEBOY_LIB  := $(SAMEBOY_ROOT)/build/lib/libsameboy.a
SAMEBOY_INC  := $(SAMEBOY_ROOT)/build/include

TEST_CC      := gcc
TEST_CFLAGS  := -std=c11 -Wall -Wextra -I$(SAMEBOY_INC) -Itest -Iwaves/src
TEST_LDFLAGS := -lm

TESTS := test/test_basic

.PHONY: all
all: $(GAME).gb

$(GAME).gb: waves/src/waves.o waves/src/envelope.o
	$(CC) $(CFLAGS) -o $@ $^
	$(ROMUSAGE) $(GAME).map

waves/src/waves.o: waves/src/waves.c waves/src/waves.h waves/src/envelope.h waves/src/protocol.h

waves/src/envelope.o: waves/src/envelope.c waves/src/envelope.h

waves/src/%.o: waves/src/%.c
	$(CC) $(CFLAGS) -c -o $@ $<

waves/src/%.o: waves/src/%.s
	$(CC) $(CFLAGS) -c -o $@ $<

.PHONY: clean
clean:
	rm -f waves/src/*.o waves/src/*.lst waves/src/*.asm waves/src/*.rst waves/src/*.sym
	rm -f *.map *.gb *.ihx *.sym *.noi
	rm -f test/*.o $(TESTS)

.PHONY: run
run:
	sameboy $(GAME).gb

.PHONY: test
test: $(GAME).gb $(TESTS)
	WAVES_ROM=$(GAME).gb test/test_basic

$(SAMEBOY_LIB):
	PATH="$(abspath tools):$$PATH" $(MAKE) -C $(SAMEBOY_ROOT) headers lib CONF=release

test/harness.o: test/harness.c test/harness.h | $(SAMEBOY_LIB)
	$(TEST_CC) $(TEST_CFLAGS) -c $< -o $@

test/test_basic.o: test/test_basic.c test/harness.h waves/src/protocol.h | $(SAMEBOY_LIB)
	$(TEST_CC) $(TEST_CFLAGS) -c $< -o $@

test/test_basic: test/test_basic.o test/harness.o $(SAMEBOY_LIB)
	$(TEST_CC) $^ $(TEST_LDFLAGS) -o $@
