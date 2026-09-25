"""Regress the directory entries required by opkg's tar extractor."""
import io
import tarfile
import unittest
from build_feed import archive


class ArchiveTest(unittest.TestCase):
    def test_parent_directories_precede_files(self):
        payload = archive({'./usr/share/v2raya-fork/README': b'example',
                           './usr/share/v2raya-fork/SECOND': b'second'})
        with tarfile.open(fileobj=io.BytesIO(payload)) as tar:
            entries = tar.getmembers()
            self.assertEqual([e.name for e in entries[:3]],
                             ['./usr', './usr/share', './usr/share/v2raya-fork'])
            self.assertTrue(all(e.isdir() and e.mode == 0o755 for e in entries[:3]))
            self.assertEqual(len(entries), 5)
            self.assertEqual(tar.extractfile(entries[3]).read(), b'example')


if __name__ == '__main__':
    unittest.main()
