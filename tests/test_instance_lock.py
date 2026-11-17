import os
import unittest
from instance_lock import acquire_instance

class InstanceLockTests(unittest.TestCase):
 @unittest.skipUnless(os.name=="nt","Windows named mutex")
 def test_duplicate_port_is_rejected_and_release_allows_restart(self):
  release=acquire_instance(49321)
  try:
   with self.assertRaises(RuntimeError):acquire_instance(49321)
  finally:release()
  release=acquire_instance(49321);release()
