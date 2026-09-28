import unittest
from unittest.mock import patch
import mode_guard as m
GOOD='Dolby HDR Info[2] Video Format[R444] DeepColorMode[ 8BIT] PHY Lock[1] is5Vconnected[1] isMute[0]'
class ModeTests(unittest.TestCase):
 def test_standard(self):self.assertTrue(m.is_standard_dv(GOOD))
 def test_other_modes(self):
  for a,b in [('Info[2]','Info[3]'),('Info[2]','Info[0]'),('R444','Y422'),('8BIT','12BIT'),('Lock[1]','Lock[0]'),('is5Vconnected[1]','is5Vconnected[0]'),('isMute[0]','isMute[1]')]:
   with self.subTest(b=b):self.assertFalse(m.is_standard_dv(GOOD.replace(a,b)))
  self.assertFalse(m.is_standard_dv(''))
 def test_only_hdr_is_changed(self):
  with patch.object(m,'rpc',side_effect=[{'info':{'components':[{'name':'HDR','enabled':False}]}},{'success':True}]) as rpc:
   m.apply(True)
   self.assertEqual(rpc.call_args.args[0],{'command':'componentstate','componentstate':{'component':'HDR','state':True}})
 def test_already_correct_no_write(self):
  with patch.object(m,'rpc',return_value={'info':{'components':[{'name':'HDR','enabled':True}]}}) as rpc:
   m.apply(True);self.assertEqual(rpc.call_count,1)
unittest.main()
