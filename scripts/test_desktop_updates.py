# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import desktop_updates as updates


def release(tag, prerelease=False, draft=False, assets=None):
    if assets is None:
        name = updates.asset_name(tag)
        assets = [name, name + '.sha256']
    return {'tag_name': tag, 'prerelease': prerelease, 'draft': draft,
            'assets': [{'name': item, 'browser_download_url': 'https://downloads.example/' + item} for item in assets]}


class SelectReleaseTests(unittest.TestCase):
    def pick(self, installed, releases):
        with patch.object(updates.platform, 'machine', return_value='arm64'), \
                patch.object(updates.sys, 'platform', 'darwin'):
            chosen = updates.select_release(releases, installed)
        return chosen and chosen['tag_name']

    def test_stable_install_ignores_prereleases(self):
        self.assertIsNone(self.pick('2.0.0', [release('v2.0.1', prerelease=True)]))

    def test_stable_install_takes_newer_stable(self):
        self.assertEqual(self.pick('2.0.0', [release('v2.0.1')]), 'v2.0.1')

    def test_prerelease_install_accepts_newer_prerelease(self):
        self.assertEqual(self.pick('2.0.0-rc.22', [release('v2.0.0-rc.23', prerelease=True)]), 'v2.0.0-rc.23')

    def test_prerelease_install_accepts_newer_stable(self):
        self.assertEqual(self.pick('2.0.0-rc.22', [release('v2.0.0')]), 'v2.0.0')

    def test_drafts_are_always_skipped(self):
        self.assertIsNone(self.pick('2.0.0', [release('v2.1.0', draft=True)]))

    def test_newest_compatible_wins(self):
        self.assertEqual(self.pick('2.0.0', [release('v2.0.1'), release('v2.0.3'), release('v2.0.2')]), 'v2.0.3')

    def test_release_without_this_platform_asset_is_skipped(self):
        self.assertIsNone(self.pick('2.0.0', [release('v2.0.1', assets=['PostForge-Desktop-2.0.1-linux-x86_64.zip'])]))

    def test_same_or_older_is_not_offered(self):
        self.assertIsNone(self.pick('2.0.1', [release('v2.0.1'), release('v2.0.0')]))

    def test_mislabelled_prerelease_tag_stays_off_stable(self):
        # prerelease flag is false, but the tag suffix marks it as a candidate build.
        self.assertIsNone(self.pick('2.0.0', [release('v2.0.1-rc.1', prerelease=False)]))


class CheckTests(unittest.TestCase):
    def run_check(self, installed, releases):
        temporary = Path(tempfile.mkdtemp())
        (temporary / 'VERSION').write_text(installed)
        reply = io.BytesIO(json.dumps(releases).encode())
        with patch.object(updates, 'ROOT', temporary), \
                patch.object(updates.urllib.request, 'urlopen', return_value=reply), \
                patch.object(updates.platform, 'machine', return_value='arm64'), \
                patch.object(updates.sys, 'platform', 'darwin'):
            return updates.check()

    def test_never_offers_legacy_packages(self):
        result = self.run_check('2.0.0', [release('v2.0.1', assets=['PostForge-2.0.1.pkg'])])
        self.assertFalse(result['available'])
        self.assertTrue(result['checked'])

    def test_offers_compatible_release_on_channel(self):
        result = self.run_check('2.0.0-rc.22', [release('v2.0.0-rc.23', prerelease=True)])
        self.assertTrue(result['available'])
        self.assertEqual(result['latest'], 'v2.0.0-rc.23')
        self.assertTrue(result['prerelease'])

    def test_network_failure_is_not_reported_current(self):
        with patch.object(updates.urllib.request, 'urlopen', side_effect=OSError):
            self.assertFalse(updates.check()['checked'])


if __name__ == '__main__':
    unittest.main()
