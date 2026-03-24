#!/usr/bin/env python3
"""Download pre-built GBDK-2020 and install it into ./tools."""

import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

GBDK_VERSION = "4.5.0"
GBDK_BASE_URL = (
    f"https://github.com/gbdk-2020/gbdk-2020/releases/download/{GBDK_VERSION}"
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")


def detect_gbdk_asset():
    """Return the GBDK release asset filename for this platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ("aarch64", "arm64"):
            return "gbdk-linux-arm64.tar.gz"
        return "gbdk-linux64.tar.gz"
    elif system == "darwin":
        if machine in ("aarch64", "arm64"):
            return "gbdk-macos-arm64.tar.gz"
        return "gbdk-macos.tar.gz"
    elif system == "windows":
        if machine in ("amd64", "x86_64"):
            return "gbdk-win64.zip"
        return "gbdk-win32.zip"
    else:
        sys.exit(f"Unsupported platform: {system} {machine}")


def download(url, dest):
    """Download *url* to *dest* with a progress indicator."""
    print(f"  Downloading {url}")
    urllib.request.urlretrieve(url, dest)


def install_gbdk():
    """Download and extract GBDK into tools/gbdk/."""
    gbdk_dir = os.path.join(TOOLS_DIR, "gbdk")
    asset = detect_gbdk_asset()
    url = f"{GBDK_BASE_URL}/{asset}"

    with tempfile.TemporaryDirectory() as tmp:
        archive_path = os.path.join(tmp, asset)
        download(url, archive_path)

        print("  Extracting...")
        if asset.endswith(".tar.gz"):
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(tmp)
        elif asset.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(tmp)

        # The archive extracts into a directory named "gbdk/"
        extracted = os.path.join(tmp, "gbdk")
        if not os.path.isdir(extracted):
            sys.exit(f"Expected extracted directory {extracted} not found")

        os.makedirs(TOOLS_DIR, exist_ok=True)
        if os.path.isdir(gbdk_dir):
            shutil.rmtree(gbdk_dir)
        shutil.move(extracted, gbdk_dir)

    print(f"GBDK {GBDK_VERSION} installed to {gbdk_dir}")


def main():
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Install directory: {TOOLS_DIR}\n")

    install_gbdk()

    print("\nDone.")


if __name__ == "__main__":
    main()
