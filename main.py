import logging
from pathlib import Path
from viewer.app import launch_editor

def _setup_logging():
    log_dir = Path.home() / ".csview"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "csview.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

if __name__ == "__main__":
    _setup_logging()
    launch_editor()
