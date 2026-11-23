"""The Anthropic API key at rest (data/output/agent/api_key, written when the Ask tab's "remember" is ticked).

Windows: encrypted with DPAPI (CryptProtectData, current-user scope, through ctypes): only this Windows account on this
computer can read it back; a copy of the file on another machine or account is useless. The file starts with MAGIC.
Linux and macOS: the key is stored as text in a file only its owner can read (mode 600): it is protected by file
permissions only, not encrypted.

A key saved as plain text by an older version is read once and rewritten in the protected form (read() migrates it).
The key is never sent back to the page: the server reports only whether one exists.
"""
import os
import sys

MAGIC = b"DNA-Analyzer DPAPI v1\n"
_ENTROPY = b"DNA-Analyzer api_key"   # a second secret DPAPI mixes in: other programs can't unprotect it blindly
_DESCRIPTION = "DNA-Analyzer API key"


# --- DPAPI (Windows) --------------------------------------------------------------------------

def _dpapi():
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    args = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(Blob)]
    crypt32.CryptProtectData.argtypes = args
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), ctypes.POINTER(wintypes.LPWSTR)] + args[2:]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    return ctypes, Blob, crypt32, kernel32


def _call(fn, data, *mid):
    ctypes, Blob, crypt32, kernel32 = _dpapi()
    buf = ctypes.create_string_buffer(data, len(data))
    ent = ctypes.create_string_buffer(_ENTROPY, len(_ENTROPY))
    blob_in = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    entropy = Blob(len(_ENTROPY), ctypes.cast(ent, ctypes.POINTER(ctypes.c_char)))
    out = Blob()
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    if not getattr(crypt32, fn)(ctypes.byref(blob_in), *mid, ctypes.byref(entropy), None, None,
                                CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
        raise OSError(f"{fn} failed: {ctypes.FormatError()}")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def protect(data):
    """DPAPI-encrypts bytes for the current Windows user."""
    return _call("CryptProtectData", data, _DESCRIPTION)


def unprotect(blob):
    """The bytes protect() encrypted; OSError when they were made by another user or machine, or were altered."""
    return _call("CryptUnprotectData", blob, None)


# --- The key file -----------------------------------------------------------------------------

def _encrypted():
    return sys.platform == "win32"


def write(path, key):
    """Saves the key: DPAPI-encrypted on Windows, mode 600 elsewhere. Written to a temporary file, then moved in place."""
    key = key.strip()
    body = MAGIC + protect(key.encode("utf-8")) if _encrypted() else key.encode("utf-8")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(body)
    if not _encrypted():
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def read(path):
    """The saved key, or None (no file, empty, or a DPAPI blob this user can't open). A plain-text key from an older
    version is rewritten in the protected form on the way."""
    try:
        with open(path, "rb") as f:
            body = f.read()
    except OSError:
        return None
    if body.startswith(MAGIC):
        if not _encrypted():
            return None
        try:
            return unprotect(body[len(MAGIC):]).decode("utf-8").strip() or None
        except (OSError, UnicodeDecodeError):
            return None
    key = body.decode("utf-8", "replace").strip()
    if not key:
        return None
    if _encrypted():
        try:
            write(path, key)   # migration: the old plain-text file, encrypted from now on
        except OSError:
            pass
    else:
        try:
            if os.stat(path).st_mode & 0o077:
                os.chmod(path, 0o600)
        except OSError:
            pass
    return key


def forget(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
