import os


def configure_qt_environment() -> None:
    """Configure Qt runtime logging to avoid noisy FFmpeg startup messages."""
    current_rules = os.environ.get("QT_LOGGING_RULES", "")
    if "qt.multimedia.ffmpeg" not in current_rules:
        if current_rules:
            os.environ["QT_LOGGING_RULES"] = f"{current_rules};qt.multimedia.ffmpeg=false"
        else:
            os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg=false"
