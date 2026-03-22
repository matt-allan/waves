# Toolchain Setup

This project uses the GBDK-2020 toolchain to compile Game Boy ROMs. The toolchain
consists of SDCC (SM83 C compiler), several support tools (lcc, bankpack, etc.), and
the GB platform library.

## Installing

Run the install script to download a pre-built GBDK release and build cppp from
source. Both are placed in `tools/`:

```sh
python3 scripts/install_tools.py
```

The Makefile defaults to `GBDK_HOME=tools/gbdk/`, so after installing you can
simply run `make`.

### Prerequisites

```sh
apt-get install -y sdcc gcc g++ clang cmake libpng-dev
```

GBDK-2020 ships its own SDCC wrapper (lcc) but relies on SDCC binaries for the
actual compilation. Distro SDCC 4.2 works for Game Boy (`-msm83:gb`) targets.

### What gets installed

| Tool | Source | Output |
|------|--------|--------|
| `cppp` | [BR903/cppp](https://github.com/BR903/cppp) (built from source) | `tools/cppp` |
| GBDK-2020 | [gbdk-2020 releases](https://github.com/gbdk-2020/gbdk-2020/releases) (pre-built) | `tools/gbdk/` |

## cppp

`cppp` ("C PreProcessor Partial") selectively strips preprocessor guards from
C headers. It is used to produce clean headers for the SameBoy test harness by
removing `GB_INTERNAL`-gated declarations without fully preprocessing the file.

Usage:
```sh
tools/cppp -D GB_INTERNAL input.h > output.h
```
