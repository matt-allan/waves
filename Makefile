GBDK_HOME ?= build/gbdk/

CC       := $(GBDK_HOME)bin/lcc
ROMUSAGE := $(GBDK_HOME)bin/romusage
CFLAGS   := -Wa-l -Wl-m -Wl-j -msm83:gb

ifdef DEBUG
	CFLAGS += -debug -v
endif

GAME := waves

SAMEBOY_ROOT := vendor/SameBoy
SAMEBOY_LIB  := $(SAMEBOY_ROOT)/build/lib/libsameboy.a
SAMEBOY_INC  := $(SAMEBOY_ROOT)/build/include

TEST_CC     := gcc
TEST_CFLAGS := -std=c11 -Wall -Wextra -I$(SAMEBOY_INC) -Itest
TEST_LDFLAGS := -lm

TESTS := test/test_basic

all: $(GAME).gb

$(GAME).gb: waves.o envelope.o
	$(CC) $(CFLAGS) -o $@ $^
	$(ROMUSAGE) $(GAME).map

waves.o: waves.c waves.h envelope.h

envelope.o: envelope.c envelope.h

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

%.o: %.s
	$(CC) $(CFLAGS) -c -o $@ $<

.PHONY: clean
clean:
	rm -f *.o *.lst *.map *.gb *.ihx *.sym *.cdb *.adb *.asm *.noi *.rst
	rm -f test/*.o $(TESTS)

.PHONY: run
run:
	sameboy $(GAME).gb

.PHONY: test
test: $(GAME).gb $(TESTS)
	WAVES_ROM=$(GAME).gb test/test_basic

test/harness.o: test/harness.c test/harness.h
	$(TEST_CC) $(TEST_CFLAGS) -c $< -o $@

test/test_basic.o: test/test_basic.c test/harness.h
	$(TEST_CC) $(TEST_CFLAGS) -c $< -o $@

test/test_basic: test/test_basic.o test/harness.o $(SAMEBOY_LIB)
	$(TEST_CC) $^ $(TEST_LDFLAGS) -o $@
