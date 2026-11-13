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
RELEASES='https://api.github.com/repos/isaacmateosv/postforge/releases'

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

def asset_name(tag):
    # The per-OS/architecture ZIP name this client would install for a release tag.
    system='windows' if sys.platform=='win32' else sys.platform
    architecture=platform.machine().lower().replace('amd64','x86_64')
    return 'PostForge-Desktop-'+(tag or '').lstrip('v')+'-'+system+'-'+architecture+'.zip'

def is_prerelease(release):
    # A release belongs to the test channel if GitHub marks it prerelease or its
    # tag carries a prerelease suffix (belt and braces, so a mislabelled tag is
    # still treated as a prerelease rather than leaking onto the stable channel).
    key=version(release.get('tag_name') or '')
    return bool(release.get('prerelease')) or (key is not None and key[3]==0)

def select_release(releases, installed):
    # Pick the newest compatible release for the installed version's channel.
    # A prerelease install (an rc/alpha/beta build) follows both prereleases and
    # stable releases; a stable install follows stable releases only. Drafts are
    # always ignored, and a release counts only if it ships this platform's ZIP.
    installed_key=version(installed)
    if installed_key is None:
        return None
    allow_prerelease=installed_key[3]==0
    best=None
    best_key=None
    for release in releases or ():
        if not isinstance(release, dict) or release.get('draft'):
            continue
        if is_prerelease(release) and not allow_prerelease:
            continue
        key=version(release.get('tag_name') or '')
        if key is None or key<=installed_key:
            continue
        names={asset.get('name') for asset in release.get('assets',[])}
        if asset_name(release.get('tag_name')) not in names:
            continue
        if best_key is None or key>best_key:
            best, best_key=release, key
    return best

def check(components=False, installed=None):
    installed=installed or (ROOT/'VERSION').read_text().strip()
    if version(installed) is None:raise ValueError('Invalid installed app version.')
    result={'installed':installed,'checked':False,'available':False}
    try:
        request=urllib.request.Request(RELEASES+'?per_page=40',headers={'User-Agent':'PostForge-desktop','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=8) as response:releases=json.load(response)
        chosen=select_release(releases,installed)
        result.update(checked=True,available=bool(chosen))
        if chosen:
            result.update(latest=chosen.get('tag_name'),compatible=True,prerelease=is_prerelease(chosen))
    except (OSError,ValueError,KeyError,TypeError):pass
    if components:
        import component_updates
        result['services']=component_updates.check()
    return result
