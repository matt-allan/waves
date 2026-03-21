SAMEBOY_ROOT := ../vendor/SameBoy
SAMEBOY_LIB  := $(SAMEBOY_ROOT)/build/lib/libsameboy.a
SAMEBOY_INC  := $(SAMEBOY_ROOT)/Core

CC     := gcc
CFLAGS := -std=c11 -Wall -Wextra -I$(SAMEBOY_INC) -I.
LDFLAGS := -lm

TESTS := test_basic

.PHONY: all clean run

all: $(TESTS)

# Build SameBoy lib if it hasn't been built yet
$(SAMEBOY_LIB):
	$(MAKE) -C $(SAMEBOY_ROOT) lib

harness.o: harness.c harness.h protocol.h | $(SAMEBOY_LIB)
	$(CC) $(CFLAGS) -c $< -o $@

test_basic.o: test_basic.c harness.h protocol.h
	$(CC) $(CFLAGS) -c $< -o $@

test_basic: test_basic.o harness.o $(SAMEBOY_LIB)
	$(CC) $^ $(LDFLAGS) -o $@

run: $(TESTS)
	./test_basic

clean:
	rm -f *.o $(TESTS)
