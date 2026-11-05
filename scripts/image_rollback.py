#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
"""Capture and restore local image IDs without exporting runtime data."""
import json
import subprocess
import sys


def command(*args):
    return subprocess.check_output(args, text=True, timeout=30).strip()


def main():
    action, path = sys.argv[1:]
    if action == 'save':
        images = command('docker', 'compose', 'config', '--images').splitlines()
        saved = {image: command('docker', 'image', 'inspect', image, '--format', '{{.Id}}') for image in images}
        with open(path, 'w') as target:
            json.dump(saved, target, indent=2)
    elif action == 'restore':
        with open(path) as source:
            images = json.load(source)
        # Check every old image exists before moving any tags.
        for image_id in images.values():
            command('docker', 'image', 'inspect', image_id, '--format', '{{.Id}}')
        for image, image_id in images.items():
            # Digest references are immutable and cannot be docker-tag destinations.
            if '@' not in image:
                command('docker', 'image', 'tag', image_id, image)
    else:
        raise ValueError('expected save or restore')


if __name__ == '__main__':
    main()
