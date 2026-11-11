# SPDX-License-Identifier: GPL-3.0-or-later
import base64
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import media_preview

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class MediaPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory();cls.root=Path(cls.temporary.name)
        cls.video=cls.root/'selected.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=red:s=160x90:r=5:d=2','-c:v','libx264','-threads','1','-pix_fmt','yuv420p',str(cls.video)],check=True)
        cls.image=cls.root/'cover.png'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(cls.video),'-frames:v','1','-threads','1',str(cls.image)],check=True)
    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()
    def test_video_dimensions_and_classification(self):
        info=media_preview.inspect(self.video)
        self.assertEqual((info['width'],info['height'],info['orientation']),(160,90,'horizontal'))
        self.assertAlmostEqual(info['duration'],2,places=1)
    def test_frame_and_uploaded_image_are_bounded_png_without_cached_files(self):
        before=set(self.root.iterdir())
        for path,second in [(self.video,1),(self.image,0)]:
            result=media_preview.frame(path,second)
            image=base64.b64decode(result['image'].split(',')[1]);self.assertTrue(image.startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertLess(len(image),3_000_000)
        self.assertEqual(set(self.root.iterdir()),before)
    def test_invalid_timestamp_does_not_start_frame_encoding(self):
        for second in (-1,2,math.inf,math.nan,'invalid'):
            with self.assertRaises(media_preview.pmlib.PMError):media_preview.frame(self.video,second)
    def test_rotation_metadata_uses_display_orientation(self):
        rotated=self.root/'rotated.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-display_rotation','90','-i',str(self.video),'-c','copy',str(rotated)],check=True)
        self.assertEqual(media_preview.inspect(rotated)['orientation'],'vertical')
    def test_nonmedia_is_rejected(self):
        private=self.root/'private.env';private.write_text('not a media file')
        with self.assertRaises(media_preview.pmlib.PMError):media_preview.inspect(private)

if __name__=='__main__':unittest.main()
