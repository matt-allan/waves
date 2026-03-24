#!/usr/bin/env python3
"""Download a specific midigram revision and vendor the files we need.

Extracts: include/midigram.h and src/midigram.c into vendor/midigram/.
"""

import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request

# Bump this to update the vendored midigram version.
MIDIGRAM_REV = "09e6db7b73d174d028ae9eb677633df101c6c9e8"

TARBALL_URL = (
    f"https://github.com/matt-allan/midigram/archive/{MIDIGRAM_REV}.tar.gz"
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VENDOR_DIR = os.path.join(REPO_ROOT, "vendor", "midigram")

# Map of archive-relative paths to vendor-relative destinations.
KEEP = {
    "include/midigram.h": "midigram.h",
    "src/midigram.c": "midigram.c",
}


def download(url: str, dest: str) -> None:
    print(f"  Downloading {url}")
    urllib.request.urlretrieve(url, dest)


def vendor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tarball = os.path.join(tmp, "midigram.tar.gz")
        download(TARBALL_URL, tarball)

        print("  Extracting...")
        with tarfile.open(tarball, "r:gz") as tf:
            # The archive has a single top-level directory:
            #   midigram-<full-sha>/
            prefix = f"midigram-{MIDIGRAM_REV}/"
            for member in tf.getmembers():
                if not member.name.startswith(prefix):
                    continue
                rel = member.name[len(prefix):]
                if rel in KEEP:
                    member.name = KEEP[rel]
                    tf.extract(member, tmp, filter="data")

        extracted = tmp

        # Wipe the old vendor dir and move files in.
        if os.path.isdir(VENDOR_DIR):
            shutil.rmtree(VENDOR_DIR)
        os.makedirs(VENDOR_DIR, exist_ok=True)

        for dest_name in KEEP.values():
            src = os.path.join(extracted, dest_name)
            dst = os.path.join(VENDOR_DIR, dest_name)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
            else:
                sys.exit(f"Expected {src} not found in archive")

    print(f"midigram {MIDIGRAM_REV[:12]} vendored to {VENDOR_DIR}")


def main() -> None:
    vendor()


if __name__ == "__main__":
    main()
