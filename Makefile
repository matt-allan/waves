ifndef GBDK_HOME
	GBDK_HOME = /opt/gbdk/
endif

CC := $(GBDK_HOME)bin/lcc
ROMUSAGE := $(GBDK_HOME)bin/romusage
CFLAGS := -Wa-l -Wl-m -Wl-j -msm83:gb

ifdef DEBUG
	CFLAGS += -debug -v
endif

GAME := waves

all: $(GAME).gb

$(GAME).gb: main.o
	$(CC) $(CFLAGS) -o $@ $^
	$(ROMUSAGE) $(GAME).map

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

.PHONY: clean
clean:
	rm -f *.o *.lst *.map *.gb *.ihx *.sym *.cdb *.adb *.asm *.noi *.rst

.PHONY: run
run:
	sameboy $(GAME).gb