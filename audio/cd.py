"""Lecture des pistes CD audio via l'API MCI de Windows."""

import ctypes
import os
import re
import struct
import numpy as np
from typing import Optional


CD_URI_RE = re.compile(r"^cdda:///(?P<drive>[A-Za-z]):/track/(?P<track>\d+)$", re.IGNORECASE)


def make_cd_uri(drive: str, track: int) -> str:
    """Construit une adresse stable pour une piste de CD."""
    return f"cdda:///{drive.rstrip(':')[:1].upper()}:/track/{int(track)}"


def parse_cd_uri(uri: str) -> Optional[tuple[str, int]]:
    match = CD_URI_RE.match(uri or "")
    if not match:
        return None
    return match.group("drive").upper() + ":", int(match.group("track"))


class CdAudio:
    """Contrôle un CD audio inséré dans un lecteur Windows."""

    alias = "solarsound_cd"

    def __init__(self):
        self._mci = ctypes.windll.winmm.mciSendStringW if os.name == "nt" else None
        self.drive = ""
        self.track = 0
        self.duration = 0.0
        self._start_ms = 0
        self._end_ms = 0
        self._opened = False

    def _command(self, command: str) -> str:
        if self._mci is None:
            raise RuntimeError("La lecture CD est disponible uniquement sous Windows")
        result = ctypes.create_unicode_buffer(256)
        error = self._mci(command, result, len(result), None)
        if error:
            raise RuntimeError(f"MCI {error}: {command}")
        return result.value.strip()

    def open(self, drive: str, track: int) -> bool:
        self.close()
        self.drive = drive.rstrip(":")[:1].upper() + ":"
        self.track = int(track)
        self._command(f'open "{self.drive}" type cdaudio alias {self.alias}')
        self._opened = True
        try:
            self._command(f"set {self.alias} time format milliseconds")
            self._start_ms = int(self._command(
                f"status {self.alias} position track {self.track}"
            ))
            length_ms = int(self._command(
                f"status {self.alias} length track {self.track}"
            ))
            self._end_ms = self._start_ms + length_ms
            self.duration = length_ms / 1000.0
            return True
        except Exception:
            self.close()
            raise

    def close(self):
        if self._opened:
            try:
                self._command(f"close {self.alias}")
            except Exception:
                pass
        self._opened = False
        self.duration = 0.0

    def play(self):
        self._command(f"play {self.alias} from {self._start_ms} to {self._end_ms}")

    def pause(self):
        self._command(f"pause {self.alias}")

    def resume(self):
        self._command(f"resume {self.alias}")

    def stop(self):
        if self._opened:
            self._command(f"stop {self.alias}")

    def seek(self, seconds: float):
        position = max(self._start_ms, min(self._end_ms, self._start_ms + int(seconds * 1000)))
        self._command(f"seek {self.alias} to {position}")

    def set_volume(self, volume: float):
        level = max(0, min(1000, int(volume * 1000)))
        self._command(f"setaudio {self.alias} volume to {level}")

    @property
    def position_seconds(self) -> float:
        if not self._opened:
            return 0.0
        try:
            current = int(self._command(f"status {self.alias} position"))
            return max(0.0, (current - self._start_ms) / 1000.0)
        except Exception:
            return 0.0

    @staticmethod
    def drives() -> list[str]:
        if os.name != "nt":
            return []
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        get_drive_type = ctypes.windll.kernel32.GetDriveTypeW
        return [
            f"{chr(65 + index)}:"
            for index in range(26)
            if mask & (1 << index)
            and get_drive_type(f"{chr(65 + index)}:\\") == 5
        ]

    def track_count(self, drive: str) -> int:
        self.close()
        normalized = drive.rstrip(":")[:1].upper() + ":"
        self._command(f'open "{normalized}" type cdaudio alias {self.alias}')
        self._opened = True
        try:
            return int(self._command(f"status {self.alias} number of tracks"))
        finally:
            self.close()

    @staticmethod
    def read_track(drive: str, track: int) -> tuple[np.ndarray, int]:
        """Extrait une piste CDDA en PCM 16 bits stéréo à 44,1 kHz."""
        if os.name != "nt":
            raise RuntimeError("L'extraction CD est disponible uniquement sous Windows")

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateFileW.restype = ctypes.c_void_p
        kernel32.DeviceIoControl.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
            ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p,
        ]
        handle = kernel32.CreateFileW(
            f"\\\\.\\{drive.rstrip(':')[:1].upper()}:" ,
            0x80000000, 0x00000001 | 0x00000002, None, 3, 0, None
        )
        if handle == ctypes.c_void_p(-1).value:
            raise OSError(f"Impossible d'ouvrir le lecteur CD {drive}")

        try:
            toc = ctypes.create_string_buffer(804)
            returned = ctypes.c_uint()
            if not kernel32.DeviceIoControl(handle, 0x00024000, None, 0,
                                            toc, len(toc), ctypes.byref(returned), None):
                raise OSError("Impossible de lire la table des pistes du CD")

            first = toc.raw[2]
            last = toc.raw[3]
            if not first <= track <= last:
                raise ValueError(f"Piste CD invalide : {track}")

            def track_lba(number: int) -> int:
                offset = 4 + (number - first) * 8
                minute, second, frame = toc.raw[offset + 5:offset + 8]
                return (minute * 60 + second) * 75 + frame - 150

            start_lba = track_lba(track)
            end_lba = track_lba(track + 1) if track < last else None
            if end_lba is None:
                cd = CdAudio()
                cd.open(drive, track)
                sectors = int(round(cd.duration * 75))
                cd.close()
            else:
                sectors = end_lba - start_lba
            if sectors <= 0:
                raise ValueError(f"Piste CD vide : {track}")

            chunks = []
            current_lba = start_lba
            remaining = sectors
            while remaining:
                count = min(27, remaining)
                # DiskOffset est un offset logique en octets (secteurs CD de 2048 octets).
                request = struct.pack("<qII", current_lba * 2048, count, 2)
                output = ctypes.create_string_buffer(count * 2352)
                if not kernel32.DeviceIoControl(
                    handle, 0x0002403E, request, len(request), output, len(output),
                    ctypes.byref(returned), None
                ):
                    raise OSError(f"Lecture brute du CD impossible (secteur {current_lba})")
                chunks.append(output.raw[:returned.value])
                current_lba += count
                remaining -= count

            raw = b"".join(chunks)
            data = np.frombuffer(raw, dtype="<i2").reshape(-1, 2).copy()
            return data, 44100
        finally:
            kernel32.CloseHandle(handle)


class CdStream:
    """Lit une piste CDDA par blocs, sans charger toute la piste en mémoire."""

    def __init__(self, drive: str, track: int):
        self.drive = drive.rstrip(":")[:1].upper() + ":"
        self.track = int(track)
        self.handle = None
        self.start_lba = 0
        self.sectors = 0
        self.position = 0

    def open(self):
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateFileW.restype = ctypes.c_void_p
        self.handle = kernel32.CreateFileW(
            f"\\\\.\\{self.drive}", 0x80000000,
            0x00000001 | 0x00000002, None, 3, 0, None
        )
        if self.handle == ctypes.c_void_p(-1).value:
            raise OSError(f"Impossible d'ouvrir le lecteur CD {self.drive}")

        try:
            toc = ctypes.create_string_buffer(804)
            returned = ctypes.c_uint()
            if not kernel32.DeviceIoControl(
                self.handle, 0x00024000, None, 0, toc, len(toc),
                ctypes.byref(returned), None
            ):
                raise OSError("Impossible de lire la table des pistes du CD")
            first, last = toc.raw[2], toc.raw[3]
            if not first <= self.track <= last:
                raise ValueError(f"Piste CD invalide : {self.track}")

            def lba(number):
                offset = 4 + (number - first) * 8
                minute, second, frame = toc.raw[offset + 5:offset + 8]
                return (minute * 60 + second) * 75 + frame - 150

            self.start_lba = lba(self.track)
            if self.track < last:
                self.sectors = lba(self.track + 1) - self.start_lba
            else:
                cd = CdAudio()
                cd.open(self.drive, self.track)
                self.sectors = int(round(cd.duration * 75))
                cd.close()
            if self.sectors <= 0:
                raise ValueError(f"Piste CD vide : {self.track}")
        except Exception:
            self.close()
            raise

    def read_chunk(self, max_sectors=27) -> Optional[np.ndarray]:
        if self.position >= self.sectors:
            return None
        count = min(max_sectors, self.sectors - self.position)
        request = struct.pack("<qII", (self.start_lba + self.position) * 2048, count, 2)
        output = ctypes.create_string_buffer(count * 2352)
        returned = ctypes.c_uint()
        ok = ctypes.windll.kernel32.DeviceIoControl(
            self.handle, 0x0002403E, request, len(request), output, len(output),
            ctypes.byref(returned), None
        )
        if not ok:
            raise OSError(f"Lecture brute du CD impossible (secteur {self.start_lba + self.position})")
        self.position += count
        return np.frombuffer(output.raw[:returned.value], dtype="<i2").reshape(-1, 2).copy()

    def seek(self, seconds: float):
        """Positionne la prochaine lecture sur une nouvelle seconde de piste."""
        sector = int(max(0.0, seconds) * 75)
        self.position = max(0, min(self.sectors, sector))

    def close(self):
        if self.handle is not None:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None
