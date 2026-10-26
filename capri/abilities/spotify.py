"""Spotify control.

With client_id/secret set (and Spotify Premium) it uses the Web API through spotipy and actually
starts the track. Without them it falls back to opening a Spotify search and using media keys.
"""
from __future__ import annotations

import os
import sys
import urllib.parse

SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing"


class Spotify:
    def __init__(self, cfg: dict):
        self.cfg = cfg["spotify"]
        self.sp = None
        if self.cfg.get("client_id") and self.cfg.get("client_secret"):
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyOAuth

                from ..config import DATA

                self.sp = spotipy.Spotify(
                    auth_manager=SpotifyOAuth(
                        client_id=self.cfg["client_id"],
                        client_secret=self.cfg["client_secret"],
                        redirect_uri=self.cfg["redirect_uri"],
                        scope=SCOPES,
                        cache_path=str(DATA / ".spotify_token"),
                    )
                )
            except Exception as e:
                print(f"[capri] spotify api unavailable, using fallback: {e}")

    # -- api path ---------------------------------------------------------
    def _device(self):
        devices = self.sp.devices().get("devices", [])
        active = [d for d in devices if d.get("is_active")]
        return (active or devices or [{}])[0].get("id")

    def play(self, query: str) -> str:
        if self.sp:
            try:
                q = query.strip()
                kind = "playlist" if "playlist" in q.lower() else "track"
                res = self.sp.search(q=q.replace("playlist", "").strip(), type=kind, limit=1)
                items = res[kind + "s"]["items"]
                if not items:
                    return f"nothing on Spotify for '{q}'"
                item = items[0]
                if kind == "playlist":
                    self.sp.start_playback(device_id=self._device(), context_uri=item["uri"])
                    return f"playing playlist {item['name']}"
                self.sp.start_playback(device_id=self._device(), uris=[item["uri"]])
                return f"playing {item['name']} by {item['artists'][0]['name']}"
            except Exception as e:
                return f"spotify error: {e}"
        _open("spotify:search:" + urllib.parse.quote(query))
        return f"opened Spotify search for {query}"

    def control(self, action: str) -> str:
        action = action.strip().lower()
        if self.sp:
            try:
                {
                    "pause": lambda: self.sp.pause_playback(),
                    "resume": lambda: self.sp.start_playback(),
                    "next": lambda: self.sp.next_track(),
                    "previous": lambda: self.sp.previous_track(),
                }[action]()
                return f"spotify {action}"
            except Exception as e:
                return f"spotify error: {e}"
        return _media_key(action)

    def now_playing(self) -> str | None:
        if not self.sp:
            return None
        try:
            cur = self.sp.current_playback()
            if cur and cur.get("item"):
                return f"{cur['item']['name']} by {cur['item']['artists'][0]['name']}"
        except Exception:
            pass
        return None


def _open(uri: str) -> None:
    """Fire and forget: launching Spotify cold can block ShellExecute for ages, and she shouldn't freeze."""
    import threading

    def go():
        try:
            if sys.platform == "win32":
                os.startfile(uri)  # type: ignore[attr-defined]
            else:
                import webbrowser

                webbrowser.open(uri)
        except Exception as e:
            print(f"[capri] couldn't open {uri}: {e}")

    threading.Thread(target=go, daemon=True).start()


def _media_key(action: str) -> str:
    if sys.platform != "win32":
        return "media keys only work on Windows"
    import ctypes

    vk = {"pause": 0xB3, "resume": 0xB3, "next": 0xB0, "previous": 0xB1}.get(action)
    if vk is None:
        return f"unknown action {action}"
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
    return f"sent {action}"
