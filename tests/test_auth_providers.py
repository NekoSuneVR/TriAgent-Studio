import unittest
from unittest.mock import patch
from app.auth import hash_password, verify, make_session, auth
from app.providers import choose_model, public_config

class AuthProviderTests(unittest.TestCase):
    def test_hash_round_trip(self):
        hashed=hash_password('very-long-example-password')
        self.assertTrue(verify('very-long-example-password',hashed))
        self.assertFalse(verify('wrong',hashed))
    def test_invalid_hash(self):
        self.assertFalse(verify('password','not-a-hash'))
    def test_short_lived_session(self):
        with patch.dict('os.environ',{'SESSION_SECRET':'x'*64}):
            bearer=make_session()
            self.assertIsNone(auth('Bearer '+bearer))
    def test_curated_free_models(self):
        self.assertEqual(choose_model('openrouter','https://example.com','token','provider/free-model,other'),'provider/free-model')
    def test_no_unverified_free_model(self):
        with self.assertRaises(RuntimeError):
            choose_model('openai','https://api.openai.com/v1','key','')
    def test_provider_inventory(self):
        self.assertIn('litellm',public_config()['providers'])
        self.assertIn('omniroute',public_config()['providers'])

if __name__=='__main__':
    unittest.main()
