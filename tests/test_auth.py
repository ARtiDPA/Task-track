import sys
import time
import unittest
import uuid
from pathlib import Path

import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from auth import Auth, AuthError, hash_password, verify_password


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.auth = Auth('test-secret-with-at-least-thirty-two-bytes', prefix='ritmo-test:'+uuid.uuid4().hex+':')
        self.auth.check()

    def tearDown(self):
        keys = list(self.auth.redis.scan_iter(self.auth.prefix+'*'))
        if keys:
            self.auth.redis.delete(*keys)
        self.auth.redis.close()

    def test_passwords_are_salted_and_verified(self):
        one, two = hash_password('correct-password'), hash_password('correct-password')
        self.assertNotEqual(one, two)
        self.assertTrue(verify_password('correct-password', one))
        self.assertFalse(verify_password('wrong-password', one))

    def test_jwt_signature_expiry_and_revocation(self):
        token, refresh = self.auth.session('alice')
        self.assertEqual(self.auth.verify('Bearer '+token), 'alice')
        claims = jwt.decode(token, self.auth.secret, algorithms=['HS256'], audience='ritmo-web')
        self.assertGreater(self.auth.redis.ttl(self.auth.prefix+'session:'+claims['sid']), 0)
        self.auth.logout(refresh)
        with self.assertRaises(AuthError):
            self.auth.verify('Bearer '+token)
        for secret, expires in [('incorrect-secret-with-thirty-two-bytes', time.time()+100),
                                 (self.auth.secret, time.time()-100)]:
            claims['exp'] = expires
            invalid = jwt.encode(claims, secret, algorithm='HS256')
            with self.assertRaises(AuthError):
                self.auth.verify('Bearer '+invalid)

    def test_refresh_rotates_and_cannot_be_replayed(self):
        token, refresh = self.auth.session('alice')
        new_token, replacement, user = self.auth.refresh(refresh)
        self.assertEqual(user, 'alice')
        self.assertEqual(self.auth.verify('Bearer '+new_token), 'alice')
        self.assertNotEqual(refresh, replacement)
        with self.assertRaises(AuthError):
            self.auth.refresh(refresh)
        self.auth.logout(replacement)
        with self.assertRaises(AuthError):
            self.auth.verify('Bearer '+token)

    def test_rate_limit_has_expiration(self):
        self.auth.rate_limit('login', 'person', 1, 60)
        with self.assertRaises(AuthError) as error:
            self.auth.rate_limit('login', 'person', 1, 60)
        self.assertEqual(error.exception.status, 429)


if __name__ == '__main__':
    unittest.main()
