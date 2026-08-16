import os
import tempfile
import time
import unittest

from service.download import cleanup_old_files, file_ttl_sec


class FileTtlTest(unittest.TestCase):
    def test_default_is_three_days(self):
        os.environ.pop("INSTALOADER_FILE_TTL_SEC", None)
        os.environ.pop("INSTALOADER_FILE_TTL_DAYS", None)
        self.assertEqual(file_ttl_sec(), 3 * 24 * 3600)

    def test_days_env(self):
        os.environ.pop("INSTALOADER_FILE_TTL_SEC", None)
        os.environ["INSTALOADER_FILE_TTL_DAYS"] = "7"
        self.assertEqual(file_ttl_sec(), 7 * 24 * 3600)
        del os.environ["INSTALOADER_FILE_TTL_DAYS"]

    def test_sec_overrides_days(self):
        os.environ["INSTALOADER_FILE_TTL_DAYS"] = "7"
        os.environ["INSTALOADER_FILE_TTL_SEC"] = "120"
        self.assertEqual(file_ttl_sec(), 120)
        del os.environ["INSTALOADER_FILE_TTL_SEC"]
        del os.environ["INSTALOADER_FILE_TTL_DAYS"]


class CleanupOldFilesTest(unittest.TestCase):
    def test_removes_only_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTALOADER_DATA"] = tmp
            files = os.path.join(tmp, "files")
            os.makedirs(files)
            old_path = os.path.join(files, "old.mp4")
            new_path = os.path.join(files, "new.mp4")
            for p in (old_path, new_path):
                with open(p, "wb") as fh:
                    fh.write(b"x")
            old_mtime = time.time() - 4 * 24 * 3600
            os.utime(old_path, (old_mtime, old_mtime))
            removed = cleanup_old_files(3 * 24 * 3600)
            self.assertEqual(removed, 1)
            self.assertFalse(os.path.isfile(old_path))
            self.assertTrue(os.path.isfile(new_path))
            os.environ.pop("INSTALOADER_DATA", None)


if __name__ == "__main__":
    unittest.main()
