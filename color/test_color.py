"""Offline numerical/CLI checks; no access to live LUTs or devices."""
import unittest,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
from build_lut import convert
class ColorTests(unittest.TestCase):
 def test_neutral_landmarks(self):
  for intensity,expected in [(0,0),(130,188),(192,245),(255,254)]:
   self.assertTrue(np.all(np.abs(convert([[intensity,128,128]]).astype(int)-expected)<=2))
 def test_gray_ramp(self):
  out=convert(np.column_stack([np.arange(256),np.full(256,128),np.full(256,128)])).astype(int)
  self.assertTrue(np.all(out[:,0]==out[:,1]) and np.all(out[:,1]==out[:,2]))
  self.assertTrue(np.all(np.diff(out,axis=0)>=0))
 def test_invalid_file_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'input';dst=Path(d)/'output';src.write_bytes(b'bad LUT');dst.write_bytes(b'keep')
   r=subprocess.run([sys.executable,str(Path(__file__).with_name('build_lut.py')),'--input',str(src),'--output',str(dst)],capture_output=True)
   self.assertNotEqual(r.returncode,0);self.assertEqual(src.read_bytes(),b'bad LUT');self.assertEqual(dst.read_bytes(),b'keep')
if __name__=='__main__':unittest.main()
