#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Read-only digest comparison for declared Docker tags; never pulls or changes tags."""
import json
import os
import signal
import subprocess
from concurrent.futures import ThreadPoolExecutor


COMMAND_TIMEOUT_SECONDS = 8


def run(args):
    try:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
    except OSError:
        return None
    try:
        output, _ = process.communicate(timeout=COMMAND_TIMEOUT_SECONDS)
        return output.strip() if process.returncode == 0 else None
    except subprocess.TimeoutExpired:
        # Docker may spawn its buildx plugin. Kill this isolated command group so
        # a plugin cannot keep the output pipe open after the parent times out.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
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


def check():
    images = run(['docker', 'compose', 'config', '--images'])
    declared = sorted(set((images or '').splitlines()))
    # Bound registry concurrency and each subprocess timeout; six serial registry waits
    # used to make an interactive check appear stalled for several minutes.
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(image_status, declared))
    updates = [{'name': image, 'kind': 'docker'} for image, state in results if state == 'changed']
    unknown = [image for image, state in results if state == 'unknown']
    return {'updates_available': bool(updates), 'components': updates,
            'docker_stack': 'Declared tags only; major-version changes require a new release.',
            'unchecked_images': unknown, 'check_complete': bool(images) and not unknown}


if __name__ == '__main__':
    print(json.dumps(check()))
