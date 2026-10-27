"""Password hashing, signed access JWTs, and revocable Redis sessions."""
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from pathlib import Path

import jwt
import redis

ACCESS_SECONDS = 15 * 60
SESSION_SECONDS = 30 * 24 * 60 * 60


class AuthError(Exception):
    def __init__(self, message='Войди в свой профиль, чтобы продолжить.', status=401):
        super().__init__(message)
        self.status = status


def email_value(data):
    value = data.get('email', '')
    if not isinstance(value, str) or len(value) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value.strip()):
        raise ValueError('Введи корректный email.')
    return value.strip().lower()


def password_value(data, registering=False):
    password = data.get('password')
    if not isinstance(password, str) or not 1 <= len(password) <= 128:
        raise ValueError('Введи пароль длиной до 128 символов.')
    if registering and len(password) < 10:
        raise ValueError('Пароль должен содержать хотя бы 10 символов.')
    return password


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return 'scrypt$16384$8$1$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(digest).decode()


def verify_password(password, encoded):
    try:
        kind, n, r, p, salt, digest = encoded.split('$')
        if kind != 'scrypt':
            return False
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(actual, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def load_secret(directory):
    configured = os.environ.get('JWT_SECRET')
    if configured:
        if len(configured.encode()) < 32:
            raise ValueError('JWT_SECRET должен содержать минимум 32 байта.')
        return configured
    path = Path(directory) / 'jwt-secret'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x', encoding='ascii') as file:
            file.write(secrets.token_urlsafe(64))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except FileExistsError:
        pass
    return path.read_text(encoding='ascii').strip()


class Auth:
    def __init__(self, secret, redis_url=None, prefix='ritmo:'):
        self.secret = secret
        self.redis = redis.Redis.from_url(redis_url or os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0'),
                                          decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        self.prefix = prefix
        self.dummy_hash = hash_password('unused-constant-time-password')

    def check(self):
        self.redis.ping()

    def rate_limit(self, scope, identity, limit, seconds):
        key = self.prefix + 'rate:' + scope + ':' + hashlib.sha256(identity.encode()).hexdigest()
        count = self.redis.eval('''
            local n=redis.call('INCR',KEYS[1])
            if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end
            return n
        ''', 1, key, seconds)
        if count > limit:
            raise AuthError('Слишком много попыток. Попробуй чуть позже.', 429)

    def access(self, user_id, session_id):
        now = int(time.time())
        return jwt.encode({'sub': user_id, 'sid': session_id, 'jti': str(uuid.uuid4()),
                           'iat': now, 'nbf': now, 'exp': now + ACCESS_SECONDS,
                           'iss': 'ritmo', 'aud': 'ritmo-web'}, self.secret, algorithm='HS256')

    def session(self, user_id):
        sid, refresh = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
        digest = hashlib.sha256(refresh.encode()).hexdigest()
        pipe = self.redis.pipeline(transaction=True)
        pipe.set(self.prefix + 'session:' + sid, user_id, ex=SESSION_SECONDS)
        pipe.set(self.prefix + 'refresh:' + digest, sid, ex=SESSION_SECONDS)
        pipe.execute()
        return self.access(user_id, sid), refresh

    def verify(self, authorization):
        if not authorization or not authorization.startswith('Bearer '):
            raise AuthError()
        try:
            claims = jwt.decode(authorization[7:], self.secret, algorithms=['HS256'],
                                issuer='ritmo', audience='ritmo-web',
                                options={'require': ['sub', 'sid', 'jti', 'iat', 'nbf', 'exp']})
            if not isinstance(claims['sid'], str) or not isinstance(claims['sub'], str):
                raise AuthError()
            owner = self.redis.get(self.prefix + 'session:' + claims['sid'])
            if owner != claims['sub']:
                raise AuthError('Сессия завершена. Войди снова.')
            return claims['sub']
        except jwt.InvalidTokenError:
            raise AuthError('Сессия истекла. Войди снова.') from None

    def refresh(self, token):
        if not token or len(token) > 256:
            raise AuthError()
        digest = hashlib.sha256(token.encode()).hexdigest()
        replacement = secrets.token_urlsafe(48)
        new_digest = hashlib.sha256(replacement.encode()).hexdigest()
        result = self.redis.eval('''
            local sid=redis.call('GET',KEYS[1])
            if not sid then return nil end
            local user=redis.call('GET',ARGV[1]..sid)
            if not user then redis.call('DEL',KEYS[1]); return nil end
            redis.call('DEL',KEYS[1])
            redis.call('SET',KEYS[2],sid,'EX',ARGV[2])
            redis.call('EXPIRE',ARGV[1]..sid,ARGV[2])
            return {user,sid}
        ''', 2, self.prefix + 'refresh:' + digest, self.prefix + 'refresh:' + new_digest,
             self.prefix + 'session:', SESSION_SECONDS)
        if not result:
            raise AuthError('Сессия завершена. Войди снова.')
        return self.access(result[0], result[1]), replacement, result[0]

    def logout(self, token):
        if not token:
            return
        digest = hashlib.sha256(token.encode()).hexdigest()
        self.redis.eval('''
            local sid=redis.call('GET',KEYS[1])
            if sid then redis.call('DEL',ARGV[1]..sid) end
            redis.call('DEL',KEYS[1])
            return 1
        ''', 1, self.prefix + 'refresh:' + digest, self.prefix + 'session:')
