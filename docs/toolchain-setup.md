# Toolchain Setup

This project uses the GBDK-2020 toolchain to compile Game Boy ROMs. The toolchain
consists of SDCC (SM83 C compiler), several support tools (lcc, bankpack, etc.), and
the GB platform library.

## Quick Start (pre-built GBDK)

The easiest path is to download the official GBDK-2020 release:

```sh
# Download and extract to /opt/gbdk (matches the default GBDK_HOME in Makefile)
curl -L https://github.com/gbdk-2020/gbdk-2020/releases/latest/download/gbdk-linux64.tar.gz \
    | sudo tar -xz -C /opt/
```

Then build normally:

```sh
make
```

## Building from Source

The submodules at `vendor/cppp` and `vendor/gbdk-2020` can be built from source.
A convenience script is provided:

```sh
./scripts/build-toolchain.sh
# Then build the project using the local toolchain:
GBDK_HOME=build/gbdk/ make
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
| SDCC binaries | distro `/usr/bin/` | `build/gbdk/bin/` (symlinks) |

### Manual build steps

```sh
# 1. Build cppp
make -C vendor/cppp CC=clang

# 2. Set up SDCC prefix (symlinks to distro binaries)
mkdir -p build/sdcc/bin build/sdcc/libexec
for bin in packihx sdar sdasgb sdcc sdcpp sdldgb sdnm sdobjcopy \
           sdranlib sdasz80 sdldz80 sdld6808 sdld; do
    ln -sf /usr/bin/$bin build/sdcc/bin/$bin
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
