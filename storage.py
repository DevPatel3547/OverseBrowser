"""Everything Overse keeps on disk, in one SQLite file.

* history   -- every page a tab finished navigating to, newest first
* bookmarks -- saved pages, unique by URL
* profiles  -- user profiles, AES-256-GCM encrypted at rest

Profiles are encrypted with the ``cryptography`` package, whose primitives are
provided by OpenSSL. The key is derived from the profile password with scrypt and a
random per-profile salt; the password itself is never stored. A wrong password, or
any change to the stored bytes, fails GCM authentication and the profile is not
loaded. History and bookmarks are stored in plain SQLite.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

DEFAULT_DB = os.path.join(os.path.expanduser("~"), ".overse", "overse.db")

# scrypt cost parameters (n=2**15, r=8, p=1: about 32 MiB and tens of milliseconds).
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**15, 8, 1
SALT_BYTES, NONCE_BYTES, KEY_BYTES = 16, 12, 32


class ProfileError(Exception):
    """Unknown profile, wrong password, or tampered profile data."""


@dataclass
class EncryptedBlob:
    salt: bytes
    nonce: bytes
    ciphertext: bytes  # includes the 16-byte GCM tag


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=KEY_BYTES, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


def encrypt(data: dict, password: str, aad: bytes = b"") -> EncryptedBlob:
    salt, nonce = os.urandom(SALT_BYTES), os.urandom(NONCE_BYTES)
    plaintext = json.dumps(data, sort_keys=True).encode("utf-8")
    ct = AESGCM(derive_key(password, salt)).encrypt(nonce, plaintext, aad)
    return EncryptedBlob(salt, nonce, ct)


def decrypt(blob: EncryptedBlob, password: str, aad: bytes = b"") -> dict:
    try:
        plaintext = AESGCM(derive_key(password, blob.salt)).decrypt(blob.nonce, blob.ciphertext, aad)
    except InvalidTag as e:
        raise ProfileError("wrong password or corrupted profile") from e
    return json.loads(plaintext)


class Storage:
    def __init__(self, path: str = DEFAULT_DB):
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                visited_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bookmarks (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS profiles (
                username TEXT PRIMARY KEY,
                salt BLOB NOT NULL,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL
            );
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ history
    def add_history(self, url: str, title: str = "") -> None:
        if not url or url == "about:blank":
            return
        last = self.conn.execute("SELECT url FROM history ORDER BY id DESC LIMIT 1").fetchone()
        if last and last[0] == url:  # reloads and redirects to the same page count once
            return
        self.conn.execute(
            "INSERT INTO history (url, title, visited_at) VALUES (?, ?, ?)", (url, title, time.time())
        )
        self.conn.commit()

    def history(self, limit: int = 500) -> list[str]:
        """Distinct URLs, most recently visited first."""
        rows = self.conn.execute(
            "SELECT url FROM history GROUP BY url ORDER BY MAX(id) DESC LIMIT ?", (limit,)
        ).fetchall()
        return [r[0] for r in rows]

    def clear_history(self) -> None:
        self.conn.execute("DELETE FROM history")
        self.conn.commit()

    # ---------------------------------------------------------------- bookmarks
    def add_bookmark(self, url: str, title: str = "") -> None:
        self.conn.execute(
            "INSERT INTO bookmarks (url, title, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(url) DO UPDATE SET title = excluded.title",
            (url, title, time.time()),
        )
        self.conn.commit()

    def remove_bookmark(self, url: str) -> None:
        self.conn.execute("DELETE FROM bookmarks WHERE url = ?", (url,))
        self.conn.commit()

    def bookmarks(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT url FROM bookmarks ORDER BY created_at, url")]

    # ----------------------------------------------------------------- profiles
    def create_profile(self, username: str, password: str, data: dict | None = None) -> None:
        if not username or not password:
            raise ProfileError("username and password are required")
        if self.conn.execute("SELECT 1 FROM profiles WHERE username = ?", (username,)).fetchone():
            raise ProfileError(f"profile {username!r} already exists")
        self._write_profile(username, password, data or {})

    def save_profile(self, username: str, password: str, data: dict) -> None:
        self.load_profile(username, password)  # only the owner can overwrite
        self._write_profile(username, password, data)

    def load_profile(self, username: str, password: str) -> dict:
        row = self.conn.execute(
            "SELECT salt, nonce, ciphertext FROM profiles WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            raise ProfileError(f"no profile named {username!r}")
        # The username is authenticated data, so a blob copied to another row will not decrypt.
        return decrypt(EncryptedBlob(*row), password, aad=username.encode("utf-8"))

    def profiles(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT username FROM profiles ORDER BY username")]

    def _write_profile(self, username: str, password: str, data: dict) -> None:
        blob = encrypt(data, password, aad=username.encode("utf-8"))
        self.conn.execute(
            "INSERT INTO profiles (username, salt, nonce, ciphertext) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(username) DO UPDATE SET salt = excluded.salt, nonce = excluded.nonce, "
            "ciphertext = excluded.ciphertext",
            (username, blob.salt, blob.nonce, blob.ciphertext),
        )
        self.conn.commit()
