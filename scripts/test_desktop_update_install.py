# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import desktop_updates
import desktop_update_install as installer
import pmlib

ZIP_BYTES = b'PK\x03\x04' + b'synthetic-desktop-build' * 64
DIGEST = hashlib.sha256(ZIP_BYTES).hexdigest()


def release(tag='v2.0.1', assets=None, prerelease=False, draft=False):
    name = installer._expected_name(tag)
    if assets is None:
        assets = [name, name + '.sha256']
    return {'tag_name': tag, 'prerelease': prerelease, 'draft': draft,
            'assets': [{'name': item, 'browser_download_url': 'https://downloads.example/' + item} for item in assets]}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
        return False


def fake_opener(release_data, digest=DIGEST, payload=ZIP_BYTES):
    # The planner now lists releases, so RELEASES returns an array; a single
    # release dict is wrapped for convenience.
    releases = release_data if isinstance(release_data, list) else [release_data]

    def opener(url, accept):
        if url.startswith(installer.RELEASES):
            return Response(json.dumps(releases).encode())
        if url.endswith('.sha256'):
            return Response((digest + '  file.zip\n').encode())
        return Response(payload)
    return opener


class VersionOrderingTests(unittest.TestCase):
    def test_release_outranks_its_prereleases(self):
        self.assertGreater(desktop_updates.version('2.0.0'), desktop_updates.version('2.0.0-rc.22'))

    def test_release_candidates_are_ordered_numerically(self):
        self.assertGreater(desktop_updates.version('2.0.0-rc.22'), desktop_updates.version('2.0.0-rc.21'))
        self.assertGreater(desktop_updates.version('2.0.0-rc.10'), desktop_updates.version('2.0.0-rc.2'))

    def test_patch_bump_is_newer(self):
        self.assertGreater(desktop_updates.version('2.0.1'), desktop_updates.version('2.0.0'))

    def test_numeric_prerelease_below_alphanumeric(self):
        self.assertGreater(desktop_updates.version('2.0.0-rc'), desktop_updates.version('2.0.0-1'))

    def test_malformed_is_none(self):
        self.assertIsNone(desktop_updates.version('not-a-version'))


class DownloadTests(unittest.TestCase):
    def with_version(self, installed):
        temporary = Path(tempfile.mkdtemp())
        (temporary / 'VERSION').write_text(installed)
        return patch.object(installer, 'ROOT', temporary)

    def test_verified_download_returns_archive_path(self):
        with self.with_version('2.0.0'), patch.object(installer, '_open', fake_opener(release())):
            result = installer.download()
        archive = Path(result['zip'])
        self.assertTrue(archive.is_file())
        self.assertEqual(archive.read_bytes(), ZIP_BYTES)
        self.assertEqual(result['version'], '2.0.1')
        self.assertEqual(result['bytes'], len(ZIP_BYTES))

    def test_checksum_mismatch_is_rejected_and_cleaned_up(self):
        bad = 'f' * 64
        with self.with_version('2.0.0'), patch.object(installer, '_open', fake_opener(release(), digest=bad)):
            with self.assertRaises(pmlib.PMError):
                installer.download()

    def test_same_or_older_version_is_declined(self):
        with self.with_version('2.0.1'), patch.object(installer, '_open', fake_opener(release(tag='v2.0.1'))):
            with self.assertRaises(pmlib.PMError):
                installer.download()

    def test_missing_platform_asset_is_declined(self):
        only_other = release(assets=['PostForge-Desktop-2.0.1-other-cpu.zip'])
        with self.with_version('2.0.0'), patch.object(installer, '_open', fake_opener(only_other)):
            with self.assertRaises(pmlib.PMError):
                installer.download()

    def test_missing_checksum_asset_is_declined(self):
        no_sha = release(assets=[installer._expected_name('v2.0.1')])
        with self.with_version('2.0.0'), patch.object(installer, '_open', fake_opener(no_sha)):
            with self.assertRaises(pmlib.PMError):
                installer.download()

    def test_oversized_download_is_stopped(self):
        with self.with_version('2.0.0'), patch.object(installer, 'MAX_BYTES', 8), \
                patch.object(installer, '_open', fake_opener(release())):
            with self.assertRaises(pmlib.PMError):
                installer.download()

    def test_prerelease_install_downloads_newest_prerelease(self):
        payload = [release(tag='v2.0.0-rc.23', prerelease=True), release(tag='v2.0.0-rc.22', prerelease=True)]
        with self.with_version('2.0.0-rc.22'), patch.object(installer, '_open', fake_opener(payload)):
            result = installer.download()
        self.assertEqual(result['version'], '2.0.0-rc.23')

    def test_stable_install_declines_a_prerelease(self):
        with self.with_version('2.0.0'), patch.object(installer, '_open', fake_opener(release(tag='v2.0.1-rc.1', prerelease=True))):
            with self.assertRaises(pmlib.PMError):
                installer.download()

    def test_https_guard_rejects_http(self):
        with self.assertRaises(pmlib.PMError):
            installer._open('http://downloads.example/file.zip', 'application/octet-stream')


if __name__ == '__main__':
    unittest.main()
