"""Analyse les BPM et les écrit dans les métadonnées des fichiers audio."""

import os
import shutil
import tempfile
import time
from typing import Callable, Optional

from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TBPM


def read_bpm_tag(path: str) -> Optional[float]:
    """Lit le BPM enregistré dans les tags d'un fichier audio."""
    audio = MutagenFile(path, easy=False)
    if audio is None or audio.tags is None:
        return None

    tags = audio.tags
    if isinstance(tags, ID3):
        values = [frame.text for frame in tags.getall("TBPM")]
    elif "tmpo" in tags:
        values = [tags["tmpo"]]
    else:
        values = [tags.get("BPM", tags.get("bpm"))]

    for value in values:
        if isinstance(value, (list, tuple)):
            candidates = value
        else:
            candidates = [value]
        for candidate in candidates:
            if candidate is None:
                continue
            try:
                return float(str(candidate).strip())
            except (TypeError, ValueError):
                continue
    return None


def estimate_bpm(path: str) -> float:
    """Estime le tempo du morceau avec librosa."""
    import librosa
    import numpy as np

    audio_data, sample_rate = librosa.load(
        path,
        sr=22050,
        mono=True,
    )
    if audio_data.size == 0:
        raise ValueError("Le fichier audio est vide.")

    onset_envelope = librosa.onset.onset_strength(
        y=audio_data,
        sr=sample_rate,
    )
    tempo = librosa.feature.tempo(
        onset_envelope=onset_envelope,
        sr=sample_rate,
    )
    tempo_values = np.asarray(tempo).reshape(-1)
    if not tempo_values.size:
        raise ValueError("Aucun tempo détectable dans ce fichier.")

    bpm = float(tempo_values[0])
    if not 30.0 <= bpm <= 300.0:
        raise ValueError(f"Tempo détecté hors plage : {bpm:.1f} BPM.")
    return round(bpm, 1)


def write_bpm_tag(path: str, bpm: float) -> None:
    """Écrit le BPM dans le tag standard correspondant au format audio."""
    audio = MutagenFile(path, easy=False)
    if audio is None:
        raise ValueError("Format audio non pris en charge pour l'écriture des tags.")
    if audio.tags is None:
        audio.add_tags()

    tags = audio.tags
    bpm_text = str(round(float(bpm), 1))
    if isinstance(tags, ID3):
        tags.delall("TBPM")
        tags.add(TBPM(encoding=3, text=[bpm_text]))
    elif "tmpo" in tags or audio.__class__.__module__.startswith("mutagen.mp4"):
        tags["tmpo"] = [int(round(float(bpm)))]
    else:
        tags["BPM"] = [bpm_text]
    audio.save()


def _format_remaining(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    if minutes:
        return f"{minutes} min {seconds} s"
    return f"{seconds} s"


def _preserve_recovery_backups(backups: dict[str, str], paths: set[str]) -> str:
    recovery_dir = tempfile.mkdtemp(prefix="solarsound-bpm-recovery-")
    for index, path in enumerate(sorted(paths), start=1):
        backup_path = backups[path]
        filename = f"{index:04d}-{os.path.basename(path)}"
        shutil.copy2(backup_path, os.path.join(recovery_dir, filename))
    return recovery_dir


def find_audio_files(
    folders: list[str],
    supported_extensions: set[str],
    report: Optional[Callable[[int, int, str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> tuple[list[str], list[str], bool]:
    """Liste les fichiers audio sans bloquer le thread de l'interface."""
    should_stop = should_stop or (lambda: False)
    paths = []
    errors = []
    seen = set()
    for folder in folders:
        if not os.path.isdir(folder):
            errors.append(f"Dossier introuvable : {folder}")
            continue
        for root, _, filenames in os.walk(
            folder,
            onerror=lambda error: errors.append(str(error)),
        ):
            for filename in filenames:
                if should_stop():
                    return paths, errors, True
                if os.path.splitext(filename)[1].lower() not in supported_extensions:
                    continue
                path = os.path.join(root, filename)
                normalized = os.path.normcase(os.path.abspath(path))
                if normalized not in seen:
                    seen.add(normalized)
                    paths.append(path)
                    if report and len(paths) % 100 == 0:
                        report(0, 0, f"Recherche des fichiers audio… ({len(paths)} trouvés)")
    return paths, errors, False


def process_bpm_files(
    paths: list[str],
    replace_existing: bool,
    report: Optional[Callable[[int, int, str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    rollback_on_stop: Optional[Callable[[], bool]] = None,
) -> dict:
    """Analyse les fichiers, avec sauvegardes temporaires pour l'annulation."""
    should_stop = should_stop or (lambda: False)
    rollback_on_stop = rollback_on_stop or (lambda: False)
    unique_paths = []
    seen = set()
    for path in paths:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized not in seen:
            seen.add(normalized)
            unique_paths.append(path)

    result = {
        "written": {},
        "skipped": 0,
        "errors": [],
        "stopped": False,
        "rolled_back": False,
        "restored": 0,
        "recovery_directory": "",
    }
    backups = {}
    recovery_paths = set()
    start_time = time.monotonic()

    def report_progress(current: int, message: str):
        if report:
            elapsed = time.monotonic() - start_time
            remaining = elapsed / current * max(0, len(unique_paths) - current)
            report(
                current,
                len(unique_paths),
                f"{message} — temps restant estimé : {_format_remaining(remaining)}",
            )

    with tempfile.TemporaryDirectory(prefix="solarsound-bpm-") as backup_dir:
        try:
            for current, path in enumerate(unique_paths, start=1):
                if should_stop():
                    result["stopped"] = True
                    break

                try:
                    existing_bpm = read_bpm_tag(path)
                    if existing_bpm is not None and not replace_existing:
                        result["skipped"] += 1
                        report_progress(
                            current,
                            f"BPM déjà présent, conservé : {os.path.basename(path)}",
                        )
                        continue

                    bpm = estimate_bpm(path)
                    if should_stop():
                        result["stopped"] = True
                        break

                    backup_path = os.path.join(backup_dir, f"{current}.audio")
                    shutil.copy2(path, backup_path)
                    backups[path] = backup_path
                    result["written"][path] = bpm
                    write_bpm_tag(path, bpm)
                    report_progress(
                        current,
                        f"{os.path.basename(path)} — {bpm:g} BPM",
                    )
                except Exception as exc:
                    backup_path = backups.get(path)
                    if backup_path:
                        try:
                            shutil.copy2(backup_path, path)
                        except OSError as restore_error:
                            recovery_paths.add(path)
                            result["errors"].append(
                                f"{path} : {exc}; restauration impossible : "
                                f"{restore_error}"
                            )
                        else:
                            backups.pop(path, None)
                            result["written"].pop(path, None)
                            result["errors"].append(f"{path} : {exc}")
                    else:
                        result["errors"].append(f"{path} : {exc}")
                    report_progress(current, f"Erreur : {os.path.basename(path)}")

            if should_stop():
                result["stopped"] = True

            if result["stopped"] and rollback_on_stop():
                not_restored = {}
                for path, backup_path in backups.items():
                    try:
                        shutil.copy2(backup_path, path)
                        result["restored"] += 1
                    except OSError as exc:
                        recovery_paths.add(path)
                        not_restored[path] = result["written"].get(path)
                        result["errors"].append(
                            f"{path} : restauration impossible : {exc}"
                        )
                result["rolled_back"] = True
                result["written"] = not_restored
            if recovery_paths:
                try:
                    result["recovery_directory"] = _preserve_recovery_backups(
                        backups,
                        recovery_paths,
                    )
                except OSError as exc:
                    result["errors"].append(
                        f"Impossible de conserver une copie de récupération : {exc}"
                    )
        except Exception:
            restore_errors = []
            for path, backup_path in backups.items():
                try:
                    shutil.copy2(backup_path, path)
                except OSError as exc:
                    restore_errors.append(f"{path} : {exc}")
            if restore_errors:
                recovery_directory = ""
                try:
                    recovery_directory = _preserve_recovery_backups(
                        backups,
                        set(backups),
                    )
                except OSError as exc:
                    restore_errors.append(
                        f"impossible de conserver les sauvegardes : {exc}"
                    )
                raise RuntimeError(
                    "Erreur pendant l'analyse et restauration incomplète : "
                    + "; ".join(restore_errors)
                    + (
                        f". Copies disponibles dans : {recovery_directory}"
                        if recovery_directory
                        else ""
                    )
                )
            raise
        if recovery_paths:
            result["errors"].append(
                "Copies de récupération conservées dans : "
                + result["recovery_directory"]
            )

    return result
