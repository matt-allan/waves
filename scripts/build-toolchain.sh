#!/bin/sh
# Build the GBDK-2020 toolchain and cppp from source.
# Output goes to build/gbdk/ and vendor/cppp/cppp.
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GBDK_BUILD="$REPO_ROOT/build/gbdk"

cd "$REPO_ROOT"

echo "==> Initialising submodules"
git submodule update --init vendor/cppp vendor/gbdk-2020

echo "==> Building cppp"
make -C vendor/cppp CC=clang

echo "==> Applying patches to vendor/gbdk-2020"
cd vendor/gbdk-2020
for patch in "$REPO_ROOT/patches/"*.patch; do
    echo "    $patch"
    git apply --check "$patch" 2>/dev/null && git apply "$patch" || echo "    (already applied, skipping)"
done
cd "$REPO_ROOT"

echo "==> Building gbdk-support tools"
make -C vendor/gbdk-2020 gbdk-support-build

echo "==> Building gbdk-lib (sm83/gb only)"
make -C vendor/gbdk-2020 gbdk-lib-build \
    SDCCDIR=/usr PORTS=sm83 PLATFORMS=gb

echo "==> Installing GBDK to $GBDK_BUILD"
make -C vendor/gbdk-2020 gbdk-install \
    SDCCDIR=/usr \
    PORTS=sm83 PLATFORMS=gb \
    BUILDDIR="$GBDK_BUILD"

echo ""
echo "Done."
