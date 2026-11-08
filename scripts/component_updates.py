#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Read-only digest comparison for declared Docker tags; never pulls or changes tags."""
import json
import os
import re
import signal
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor


COMMAND_TIMEOUT_SECONDS = 8
EVOLUTION_RELEASE = 'https://api.github.com/repos/evolution-foundation/evolution-api/releases/latest'
EVOLUTION_PIN = 'evoapicloud/evolution-api@sha256:966625532d9076a2381e973a271307d107e6f070450de3abeeea8bd18be07252'
EVOLUTION_VERSION = '2.3.7'


def run(args):
    try:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}))
    except OSError:
        return None
    try:
        output, _ = process.communicate(timeout=COMMAND_TIMEOUT_SECONDS)
        return output.strip() if process.returncode == 0 else None
    except subprocess.TimeoutExpired:
        # Docker may spawn its buildx plugin. Kill this isolated command group so
        # a plugin cannot keep the output pipe open after the parent times out.
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except (OSError, subprocess.SubprocessError):
            process.kill()
            pass
        process.communicate()
        return None


def image_status(image):
    local = run(['docker', 'image', 'inspect', image, '--format', '{{json .RepoDigests}}'])
    try:
        digests = [item.rsplit('@', 1)[-1] for item in json.loads(local)]
        if not digests:
            return image, 'unknown'
        # A declared digest is immutable: checking the registry cannot discover a newer tag.
        if '@sha256:' in image and image.rsplit('@', 1)[-1] in digests:
            return image, 'current'
        remote = run(['docker', 'buildx', 'imagetools', 'inspect', image, '--format', '{{json .Manifest}}'])
        digest = json.loads(remote)['digest']
        return image, 'current' if digest in digests else 'changed'
    except (ValueError, TypeError, KeyError):
        return image, 'unknown'


def stable_version(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value or "")
    return tuple(map(int, match.groups())) if match else None


def evolution_status(declared):
    image = next((image for image in declared if image.startswith("evoapicloud/evolution-api")), "")
    installed = EVOLUTION_VERSION if image == EVOLUTION_PIN else None
    if installed is None and image:
        response = run([(shutil.which("curl") or "curl"), "-fsS", "--max-time", "5", "http://127.0.0.1:8080/"])
        try:
            installed = json.loads(response).get("version")
        except (ValueError, TypeError, AttributeError):
            pass
    remote = run([(shutil.which("curl") or "curl"), "-fsS", "--max-time", "6", EVOLUTION_RELEASE])
    try:
        release = json.loads(remote)
        latest = release.get("tag_name") if not release.get("prerelease") and not release.get("draft") else None
    except (ValueError, TypeError, AttributeError):
        latest = None
    current_version, latest_version = stable_version(installed), stable_version(latest)
    if current_version is None or latest_version is None:
        return None
    return {"installed": installed, "latest": latest.lstrip("v"), "update_available": latest_version > current_version}


def check():
    images = run(['docker', 'compose', 'config', '--images'])
    declared = sorted(set((images or '').splitlines()))
    # Bound registry concurrency and each subprocess timeout; six serial registry waits
    # used to make an interactive check appear stalled for several minutes.
    with ThreadPoolExecutor(max_workers=3) as pool:
        evolution = pool.submit(evolution_status, declared)
        results = list(pool.map(image_status, declared))
    updates = [{'name': image, 'kind': 'docker'} for image, state in results if state == 'changed']
    unknown = [image for image, state in results if state == 'unknown']
    return {'updates_available': bool(updates), 'components': updates,
            'docker_stack': 'Declared tags only; major-version changes require a new release.',
            'unchecked_images': unknown, 'check_complete': bool(images) and not unknown,
            'evolution': evolution.result()}


if __name__ == '__main__':
    print(json.dumps(check()))
