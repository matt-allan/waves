# Contributing

## Getting Started

Clone the repository and initialize submodules:

```sh
git clone <repo>
cd waves
git submodule update --init --recursive
```

Install host build dependencies (Ubuntu/Debian):

```sh
sudo apt install sdcc gcc clang cmake libpng-dev
```

Build the toolchain once:

```sh
make -C vendor/gbdk-2020 ...   # see Makefile for exact targets
```

Then build the ROM:

```sh
make
```

Run the test suite:

```sh
make test
```

## Code Style

Formatting is enforced by `.clang-format`. Run clang-format before submitting
changes. The configuration is:

- Indent with tabs (8-column width)
- 80-column line limit
- Linux brace style (opening brace on same line, except for function definitions)
- No short if-statements or functions on a single line

The source files in `src/` (i.e. `waves.c`, `envelope.c`, and their headers)
are the style reference. The test harness in `test/` predates some of these
conventions and should not be used as a guide.

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

Prefer a `static inline` helper function over a function-like macro. Inline
functions give you type safety, work naturally with the debugger, and do not
have the usual macro pitfalls around argument evaluation. Reserve macros for
things that genuinely cannot be done with a function.

Avoid conditional compilation (`#ifdef`, `#if`) except where it is unavoidable,
such as include guards or platform detection already present in the codebase.

### Comments

Document non-obvious hardware behaviour and any tricky algorithmic decisions.
Avoid restating what the code already says clearly. Public API declarations in
headers use `/** ... */` doc-comment blocks; inline comments use `/* ... */`.

## Submitting Changes

Open a pull request against `main`. The CI pipeline will build the ROM and run
the test suite. Both must pass before a PR can be merged.

Write commit messages in the imperative mood with a short subject line
(≤ 72 characters). Add a blank line before any extended description.
