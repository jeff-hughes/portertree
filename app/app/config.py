import os

MAIL_SERVER = os.environ.get("MAIL_SERVER")
MAIL_PORT = int(os.environ.get("MAIL_PORT"))
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS").lower() in ['true', '1', 't']
MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL").lower() in ['true', '1', 't']
MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")
MAIL_TO_ADDRESS = os.environ.get("MAIL_DEFAULT_SENDER")

_mail_opts = {
    "MAIL_SERVER": MAIL_SERVER,
    "MAIL_PORT": MAIL_PORT,
    "MAIL_USERNAME": MAIL_USERNAME,
    "MAIL_PASSWORD": MAIL_PASSWORD,
    "MAIL_USE_TLS": MAIL_USE_TLS,
    "MAIL_USE_SSL": MAIL_USE_SSL,
    "MAIL_DEFAULT_SENDER": MAIL_DEFAULT_SENDER,
    "MAIL_TO_ADDRESS": MAIL_TO_ADDRESS
}
for opt, val in _mail_opts.items():
    if val is None:
        raise ValueError(f"{opt} is not set for Flask-Mailman")