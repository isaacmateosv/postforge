#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a platform-native desktop artifact with embedded UI and legal notices."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def third_party(cargo):
    metadata = json.loads(run(cargo, "metadata", "--locked", "--offline", "--format-version", "1",
                              "--filter-platform", run("rustc", "-vV").split("host: ")[1].splitlines()[0],
                              "--manifest-path", str(HERE / "Cargo.toml")))
    sections = []
    for package in sorted(metadata["packages"], key=lambda value: (value["name"], value["version"])):
        if not package.get("source"):
            continue
        folder = Path(package["manifest_path"]).parent
        texts = []
        candidates = set()
        for pattern in ("LICENSE*", "LICENCE*", "COPYING*", "NOTICE*"):
            candidates.update(folder.glob(pattern))
        if package.get("license_file"):
            candidates.add(folder / package["license_file"])
        for file in sorted(candidates):
            if file.is_file():
                texts.append(file.name + "\n" + file.read_text(encoding="utf-8", errors="replace"))
        title = package["name"] + " " + package["version"] + " · " + (package.get("license") or "See included license")
        sections.append(title + "\n" + (package.get("repository") or "") + "\n\n" + "\n\n".join(texts))
    return "\n\n" + ("\n\n" + "=" * 72 + "\n\n").join(sections)


def icon(output):
    existing = ROOT / "tray/build/PostForge.app/Contents/Resources/PostForge.icns"
    if existing.is_file():
        shutil.copyfile(existing, output)
        return
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary) / "PostForge.iconset"
        folder.mkdir()
        for size in (16, 32, 128, 256, 512):
            for multiplier, suffix in ((1, ""), (2, "@2x")):
                pixels = str(size * multiplier)
                subprocess.run(["sips", "-z", pixels, pixels, str(HERE / "ui/mark.png"),
                                "--out", str(folder / f"icon_{size}x{size}{suffix}.png")],
                               check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["iconutil", "-c", "icns", str(folder), "-o", str(output)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    version = (ROOT / "VERSION").read_text().strip()
    configured = json.loads((HERE / "tauri.conf.json").read_text())
    manifest_version = re.search(r'^version = "([^"]+)"', (HERE / "Cargo.toml").read_text(), re.M)[1]
    if configured["version"] != version or manifest_version != version:
        raise SystemExit("Rust, desktop config, and project versions must agree.")
    cargo = shutil.which("cargo")
    if not cargo:
        raise SystemExit("Install Rust and add Cargo to PATH before building.")
    if not args.no_build:
        subprocess.run([cargo, "build", "--release", "--locked", "--manifest-path", str(HERE / "Cargo.toml")], check=True)
    executable = HERE / "target/release" / ("postforge-desktop.exe" if os.name == "nt" else "postforge-desktop")
    output = HERE / "dist"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        if sys.platform == "darwin":
            app = stage / "PostForge Desktop.app"
            binary_dir = app / "Contents/MacOS"
            resources = app / "Contents/Resources"
            binary_dir.mkdir(parents=True)
            resources.mkdir()
            shutil.copy2(executable, binary_dir / "postforge-desktop")
            info = {"CFBundleName": "PostForge Desktop", "CFBundleDisplayName": "PostForge Desktop",
                    "CFBundleIdentifier": "local.postforge.desktop", "CFBundleExecutable": "postforge-desktop",
                    "CFBundlePackageType": "APPL", "CFBundleShortVersionString": version,
                    "CFBundleVersion": version, "LSMinimumSystemVersion": "13.0",
                    "NSHighResolutionCapable": True, "CFBundleIconFile": "PostForge",
                    "NSHumanReadableCopyright": "Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors"}
            (app / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
            icon(resources / "PostForge.icns")
        else:
            app = stage / "PostForge Desktop"
            app.mkdir()
            resources = app
            shutil.copy2(executable, app / executable.name)
        for name in ("LICENSE", "COPYRIGHT", "NOTICE.md"):
            shutil.copyfile(ROOT / name, resources / name)
        (resources / "THIRD_PARTY_NOTICES.txt").write_text(third_party(cargo), encoding="utf-8")
        shutil.copytree(ROOT / "docs/help", resources / "Help")
        sys.path.insert(0,str(ROOT / "scripts"))
        import runtime_install
        runtime_install.build(ROOT,resources / "Runtime")
        if sys.platform == "darwin":
            subprocess.run(["codesign", "--force", "--sign", "-", str(app)], check=True)
            subprocess.run(["codesign", "--verify", "--strict", str(app)], check=True)
        system = "windows" if os.name == "nt" else sys.platform
        architecture = platform.machine().lower().replace("amd64", "x86_64")
        target = output / ("PostForge-Desktop-" + version + "-" + system + "-" + architecture + ".zip")
        if sys.platform == "darwin":
            subprocess.run(["ditto", "-c", "-k", "--keepParent", str(app), str(target)], check=True)
        else:
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                for file in sorted(app.rglob("*")):
                    if file.is_file():
                        archive.write(file, file.relative_to(stage))
        if sys.platform == "darwin":
            package_root=stage / "installer-root"
            applications=package_root / "Applications";applications.mkdir(parents=True)
            shutil.copytree(app,applications / app.name)
            package=output / ("PostForge-Desktop-"+version+"-darwin-"+architecture+".pkg")
            import installer
            installer.build(package_root,package,version,architecture,stage)
            package.with_suffix(".pkg.sha256").write_text(hashlib.sha256(package.read_bytes()).hexdigest()+"  "+package.name+"\n")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        target.with_suffix(target.suffix + ".sha256").write_text(digest + "  " + target.name + "\n")
        print(target)


if __name__ == "__main__":
    main()
