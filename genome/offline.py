"""Offline mode: with DNA_OFFLINE set, no network connection leaves the process.

    DNA_OFFLINE=1 python -m cluster_analysis.profiles run      # every lookup must come from local files
    DNA_OFFLINE=1 DNA_OFFLINE_LOG=misses.txt python -m ...       # also list each blocked request, one per line

A person's analysis should only look things up in the knowledge base on disk. In offline mode any attempt to reach
the network raises Offline, naming the URL, instead of fetching it: a gap in the knowledge base shows up as an error,
not as a quiet API call. Installed when the genome or cluster_analysis package is imported.
"""
import os
import socket
import threading

_lock = threading.Lock()


class Offline(OSError):
    """A network request in offline mode."""


def _blocked(what):
    log = os.environ.get("DNA_OFFLINE_LOG")
    if log:
        with _lock, open(log, "a", encoding="utf-8") as f:
            f.write(what + "\n")
    raise Offline(f"offline mode (DNA_OFFLINE): blocked {what}")


def install():
    if not os.environ.get("DNA_OFFLINE") or getattr(socket, "_dna_offline", False):
        return
    socket._dna_offline = True
    # The full URL where a library hands it over; the socket as the backstop for anything else
    try:
        import requests.adapters
        requests.adapters.HTTPAdapter.send = lambda self, request, *a, **k: _blocked(f"{request.method} {request.url}")
    except ImportError:
        pass
    import urllib.request
    urllib.request.OpenerDirector.open = lambda self, url, *a, **k: _blocked(
        f"GET {url if isinstance(url, str) else url.full_url}")
    real_connect = socket.socket.connect

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            _blocked(f"socket {address}")
        return real_connect(self, address)
    socket.socket.connect = connect
    socket.create_connection = lambda address, *a, **k: _blocked(f"socket {address}")
