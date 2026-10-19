import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import storage  # noqa: E402
from storage import ProfileError, Storage  # noqa: E402


@pytest.fixture(autouse=True)
def fast_kdf(monkeypatch):
    monkeypatch.setattr(storage, "SCRYPT_N", 2**10)  # keep the tests quick


@pytest.fixture
def db(tmp_path):
    s = Storage(str(tmp_path / "overse.db"))
    yield s
    s.close()


def test_history_persists_across_restarts(tmp_path):
    path = str(tmp_path / "overse.db")
    s = Storage(path)
    s.add_history("https://a.example/", "A")
    s.add_history("https://a.example/", "A")  # a reload is one visit
    s.add_history("https://b.example/", "B")
    s.add_history("https://a.example/", "A")
    s.close()
    s = Storage(path)
    assert s.history() == ["https://a.example/", "https://b.example/"]
    assert s.conn.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 3
    s.clear_history()
    assert s.history() == []


def test_blank_pages_are_not_history(db):
    db.add_history("about:blank")
    db.add_history("")
    assert db.history() == []


def test_bookmarks_are_unique_and_removable(db):
    db.add_bookmark("https://a.example/", "A")
    db.add_bookmark("https://a.example/", "A again")
    db.add_bookmark("https://b.example/", "B")
    assert db.bookmarks() == ["https://a.example/", "https://b.example/"]
    db.remove_bookmark("https://a.example/")
    assert db.bookmarks() == ["https://b.example/"]


def test_profile_round_trip(db):
    db.create_profile("dev", "correct horse", {"homepage": "https://dev.example/"})
    assert db.load_profile("dev", "correct horse") == {"homepage": "https://dev.example/"}
    db.save_profile("dev", "correct horse", {"homepage": "https://new.example/"})
    assert db.load_profile("dev", "correct horse")["homepage"] == "https://new.example/"
    assert db.profiles() == ["dev"]


def test_profile_is_not_plaintext_on_disk(tmp_path):
    path = tmp_path / "overse.db"
    s = Storage(str(path))
    s.create_profile("dev", "correct horse", {"homepage": "https://secret-home.example/"})
    s.close()
    raw = path.read_bytes()
    assert b"secret-home" not in raw
    assert b"correct horse" not in raw  # the password is never stored
    cols = [r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(profiles)")]
    assert "password" not in cols


def test_wrong_password_is_rejected(db):
    db.create_profile("dev", "correct horse", {})
    with pytest.raises(ProfileError):
        db.load_profile("dev", "wrong")
    with pytest.raises(ProfileError):
        db.save_profile("dev", "wrong", {"homepage": "x"})


def test_tampered_or_moved_ciphertext_is_rejected(db):
    db.create_profile("alice", "pw-a", {"homepage": "a"})
    db.create_profile("mallory", "pw-m", {"homepage": "m"})
    ct = bytearray(db.conn.execute("SELECT ciphertext FROM profiles WHERE username='alice'").fetchone()[0])
    ct[0] ^= 1
    db.conn.execute("UPDATE profiles SET ciphertext=? WHERE username='alice'", (bytes(ct),))
    with pytest.raises(ProfileError):
        db.load_profile("alice", "pw-a")
    # Copying mallory's row under another name fails: the username is authenticated data.
    salt, nonce, ct = db.conn.execute("SELECT salt, nonce, ciphertext FROM profiles WHERE username='mallory'").fetchone()
    db.conn.execute("UPDATE profiles SET salt=?, nonce=?, ciphertext=? WHERE username='alice'", (salt, nonce, ct))
    with pytest.raises(ProfileError):
        db.load_profile("alice", "pw-m")


def test_duplicate_or_empty_profiles_are_refused(db):
    db.create_profile("dev", "pw", {})
    with pytest.raises(ProfileError):
        db.create_profile("dev", "other", {})
    with pytest.raises(ProfileError):
        db.create_profile("", "pw", {})
    with pytest.raises(ProfileError):
        db.load_profile("nobody", "pw")


def test_each_profile_gets_its_own_salt_and_nonce(db):
    db.create_profile("a", "same", {})
    db.create_profile("b", "same", {})
    rows = db.conn.execute("SELECT salt, nonce FROM profiles").fetchall()
    assert rows[0][0] != rows[1][0] and rows[0][1] != rows[1][1]
