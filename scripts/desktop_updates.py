# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, read-only desktop release checks; never offers legacy app packages."""
import json
import platform
import re
import sys
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent

def version(value):
    # A comparable semver key: core numbers, then a final-release flag (a release
    # outranks any prerelease of the same core), then dotted prerelease identifiers
    # ordered as semver requires (numeric below alphanumeric, numerics compared as
    # numbers). This lets rc.21 → rc.22 be seen as newer, not merely equal.
    found=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-([\w.-]+))?',value or '')
    if not found:return None
    core=tuple(map(int,found.groups()[:3]))
    prerelease=found[4]
    if prerelease is None:
        return (*core,1,())
    identifiers=tuple((0,int(part)) if part.isdigit() else (1,part) for part in prerelease.split('.'))
    return (*core,0,identifiers)

def check(components=False):
    installed=(ROOT/'VERSION').read_text().strip()
    result={'installed':installed,'checked':False,'available':False}
    try:
        request=urllib.request.Request('https://api.github.com/repos/isaacmateosv/postforge/releases/latest',headers={'User-Agent':'PostForge-desktop','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=8) as response:release=json.load(response)
        latest=release['tag_name'];system='windows' if sys.platform=='win32' else sys.platform
        architecture=platform.machine().lower().replace('amd64','x86_64')
        expected='PostForge-Desktop-'+latest.lstrip('v')+'-'+system+'-'+architecture+'.zip'
        compatible=any(asset.get('name')==expected for asset in release.get('assets',[]))
        result.update(checked=True,latest=latest,compatible=compatible,available=bool(compatible and version(latest) and version(installed) and version(latest)>version(installed)))
    except (OSError,ValueError,KeyError):pass
    if components:
        import component_updates
        result['services']=component_updates.check()
    return result
