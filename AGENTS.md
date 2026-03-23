# Contributing

## Getting Started

Initialize submodules:

```sh
git submodule update --init --recursive
```

Install host build dependencies (Ubuntu/Debian):

```sh
sudo apt install sdcc gcc clang cmake libpng-dev ninja-build
```

Install Python dependencies:

```sh
uv sync
```

Install the toolchain (GBDK and cppp) into `tools/`:

```sh
uv run python scripts/install_tools.py
```

Then build the ROM:

```sh
uv run python configure.py
ninja
```

Run the test suite:

```sh
ninja build/lib/libsameboy.so && uv run pytest
```

## Guidelines

Be mindful of CPU cycles and flash size.

## Code Style

Formatting is enforced by `clang-format`.

### Naming

- Functions and variables: `lower_snake_case`
- Enum values and constants: `UPPER_SNAKE_CASE`
- Struct and enum types: `lower_snake_case`

### Constants

Use `const` variables or `enum` values instead of `#define` for named
constants. `enum` is preferred when the constant is used as an array size or
grouped with related values. Avoid `#define` unless there is no alternative
(e.g. stringification or token pasting).

### Macros and Preprocessor

Prefer a `static inline` helper function over a function-like macro.

Avoid conditional compilation (`#ifdef`, `#if`) except where it is unavoidable,
such as include guards or platform detection.

### Comments

Explain why, not just what.

Document any non-obvious hardware behaviour.

## Submitting Changes

Open a pull request against `main`. The CI pipeline will build the ROM and run tests.
