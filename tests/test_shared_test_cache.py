import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from shared_test_cache import materialize, blob_id

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache = self.root / "cache"
        self.cache.mkdir(mode=0o700)
        self.data = {"shared_test_execution.py": b"engine", "shared_test_result.py": b"result"}
        self.blobs = {k: blob_id(v) for k,v in self.data.items()}
        self.calls = []
    def fetch(self, commit, name, expected):
        self.calls.append(name)
        return self.data[name]
    def run_cache(self, name, commit="a"*40, fetch=None):
        dest = self.root / name
        dest.mkdir(mode=0o700)
        return materialize(self.cache, dest, commit=commit, blobs=self.blobs, fetch=fetch or self.fetch)
    def test_cold_and_offline_warm_hit(self):
        self.assertEqual(self.run_cache("a")["misses"],2)
        self.assertEqual(self.run_cache("b",fetch=lambda *args: self.fail("network on cache hit"))["hits"],2)
        self.assertEqual((self.root/"b"/"shared_test_execution.py").read_bytes(),b"engine")
    def test_new_version_is_independent(self):
        self.run_cache("a")
        self.assertEqual(self.run_cache("b",commit="b"*40)["misses"],2)
    def test_tampered_cache_fails_closed(self):
        self.run_cache("a")
        (self.cache/"public-engine-cache"/("a"*40)/"shared_test_execution.py").write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError,"CACHE_IDENTITY_MISMATCH"):
            self.run_cache("b")
    def test_symlink_denied(self):
        self.run_cache("a")
        p=self.cache/"public-engine-cache"/("a"*40)/"shared_test_execution.py"
        p.unlink()
        p.symlink_to(self.root/"a"/"shared_test_execution.py")
        with self.assertRaises(OSError):
            self.run_cache("b")
    def test_bad_download_not_published(self):
        with self.assertRaisesRegex(ValueError,"DOWNLOAD_IDENTITY_MISMATCH"):
            self.run_cache("a",fetch=lambda *args: b"bad")
        self.assertEqual(self.run_cache("b")["misses"],2)
    def test_unsafe_parent_denied(self):
        os.chmod(self.cache,0o755)
        with self.assertRaisesRegex(ValueError,"CACHE_DIRECTORY_UNSAFE"):
            self.run_cache("a")
