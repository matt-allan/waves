# Toolchain Setup

This project uses the GBDK-2020 toolchain to compile Game Boy ROMs. The toolchain
consists of SDCC (SM83 C compiler), several support tools (lcc, bankpack, etc.), and
the GB platform library.

## Building from Source (default)

The Makefile defaults to `GBDK_HOME=build/gbdk/`. Run the build script once to
populate it, then `make` works without any extra flags:

```sh
./scripts/build-toolchain.sh
make
```

### Prerequisites

```sh
apt-get install -y sdcc gcc g++ clang cmake libpng-dev
```

GBDK-2020 ships its own SDCC wrapper (lcc) but relies on SDCC binaries for the
actual compilation. Distro SDCC 4.2 works for Game Boy (`-msm83:gb`) targets.
GBDK's warning about "not using distro SDCC" applies to platforms needing their
custom SDCC patches (Sega GG/SMS, NES); it is fine for Game Boy.

### What gets built

| Tool | Source | Output |
|------|--------|--------|
| `cppp` | `vendor/cppp` | `vendor/cppp/cppp` |
| `lcc` | `vendor/gbdk-2020/gbdk-support/lcc` | `build/gbdk/bin/lcc` |
| `bankpack` | `vendor/gbdk-2020/gbdk-support/bankpack` | `build/gbdk/bin/bankpack` |
| `png2asset` | `vendor/gbdk-2020/gbdk-support/png2asset` | `build/gbdk/bin/png2asset` |
| `romusage` | `vendor/gbdk-2020/gbdk-support/romusage` | `build/gbdk/bin/romusage` |
| `gb.lib` + `crt0.o` | `vendor/gbdk-2020/gbdk-lib` | `build/gbdk/lib/gb/` |
| SDCC binaries | distro `/usr/bin/` | `build/gbdk/bin/` (copied) |

### Manual build steps

```sh
# 1. Build cppp
make -C vendor/cppp CC=clang

# 2. Copy SDCC binaries into isolated prefix
mkdir -p build/sdcc/bin build/sdcc/libexec
for bin in packihx sdar sdasgb sdcc sdcpp sdldgb sdnm sdobjcopy \
           sdranlib sdasz80 sdldz80 sdld6808 sdld; do
    cp /usr/bin/$bin build/sdcc/bin/$bin
done

# 3. Build gbdk-support tools
make -C vendor/gbdk-2020 gbdk-support-build

# 4. Build gbdk-lib for Game Boy only
make -C vendor/gbdk-2020 gbdk-lib-build \
    SDCCDIR=$(pwd)/build/sdcc PORTS=sm83 PLATFORMS=gb

# 5. Install everything into build/gbdk/
make -C vendor/gbdk-2020 gbdk-install \
    SDCCDIR=$(pwd)/build/sdcc \
    PORTS=sm83 PLATFORMS=gb \
    BUILDDIR=$(pwd)/build/gbdk
```

## Patches

Patches for vendor code are stored in `patches/`. They are applied automatically
by `scripts/build-toolchain.sh` but are tracked here for reference.

| Patch | Applies to | Reason |
|-------|-----------|--------|
| `0001-gbdk-2020-sprintf-sdcc42-compat.patch` | `vendor/gbdk-2020` | SDCC 4.2 rejects variable declarations directly in `case` without a block; add braces around `case 'c'` in `sprintf.c`. |

## cppp

`cppp` ("C PreProcessor Partial") selectively strips preprocessor guards from
C headers. It is used to produce clean headers for the SameBoy test harness by
removing `GB_INTERNAL`-gated declarations without fully preprocessing the file.

Build output: `vendor/cppp/cppp`

Usage:
```sh
vendor/cppp/cppp -D GB_INTERNAL input.h > output.h
```
