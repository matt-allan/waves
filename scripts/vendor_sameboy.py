#!/usr/bin/env python3
"""Download a specific SameBoy revision and vendor the files we need.

Extracts: LICENSE, version.mk, and the Core/ directory into vendor/sameboy/.
"""

import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request

# Bump this to update the vendored SameBoy version.
SAMEBOY_REV = "208ba4afabffab9edde416f2dbb8ae459e34adb8"

TARBALL_URL = (
    f"https://github.com/LIJI32/SameBoy/archive/{SAMEBOY_REV}.tar.gz"
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VENDOR_DIR = os.path.join(REPO_ROOT, "vendor", "sameboy")

# Only these top-level entries are extracted from the archive.
KEEP = {"LICENSE", "version.mk", "Core"}


def download(url: str, dest: str) -> None:
    print(f"  Downloading {url}")
    urllib.request.urlretrieve(url, dest)


def vendor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tarball = os.path.join(tmp, "sameboy.tar.gz")
        download(TARBALL_URL, tarball)

        print("  Extracting...")
        with tarfile.open(tarball, "r:gz") as tf:
            # The archive has a single top-level directory:
            #   SameBoy-<full-sha>/
            prefix = f"SameBoy-{SAMEBOY_REV}/"
            for member in tf.getmembers():
                if not member.name.startswith(prefix):
                    continue
                rel = member.name[len(prefix) :]
                top = rel.split("/")[0] if rel else ""
                if top not in KEEP:
                    continue
                member.name = rel
                tf.extract(member, tmp, filter="data")

        extracted = tmp

        # Wipe the old vendor dir and move files in.
        if os.path.isdir(VENDOR_DIR):
            shutil.rmtree(VENDOR_DIR)
        os.makedirs(VENDOR_DIR, exist_ok=True)

        for name in KEEP:
            src = os.path.join(extracted, name)
            dst = os.path.join(VENDOR_DIR, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            elif os.path.isfile(src):
                shutil.copy2(src, dst)
            else:
                sys.exit(f"Expected {src} not found in archive")

    print(f"SameBoy {SAMEBOY_REV[:12]} vendored to {VENDOR_DIR}")


def main() -> None:
    vendor()


if __name__ == "__main__":
    main()
