import hashlib
import os
from flask_login.mixins import UserMixin

admin_salt = os.environb.get(b"APP_ADMIN_SALT").decode("unicode-escape").encode("latin-1")

class User(UserMixin):
    admin_user = os.environ.get("APP_ADMIN_USER")
    admin_pass = os.environb.get(b"APP_ADMIN_PASS").decode("unicode-escape").encode("latin-1")
    admin_salt = admin_salt

    def __init__(self, username, password):
        super().__init__()
        self.id = username
        self.password = password

    @classmethod
    def get(cls, uid):
        return User(cls.admin_user, cls.admin_pass)


def hash_pass(password):
    pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
        admin_salt, 100000)
    return pw_hash