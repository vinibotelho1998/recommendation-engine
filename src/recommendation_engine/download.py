"""Opt-in download of the official MovieLens small archive."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .data import load_dataset

DATASET_PAGE = "https://grouplens.org/datasets/movielens/latest/"
ARCHIVE_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
README_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small-README.html"


def download_movielens(target: str | Path, accept_license: bool = False) -> Path:
    if not accept_license:
        raise ValueError(
            f"Read the MovieLens terms at {README_URL}, then pass --accept-license. "
            "MovieLens data is not covered by this project's code license."
        )
    target = Path(target)
    if target.exists() and any(target.iterdir()):
        raise ValueError("Destination is not empty; choose another output directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "recommendation-engine/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        archive = response.read(8 * 1024 * 1024 + 1)
    if len(archive) > 8 * 1024 * 1024:
        raise ValueError("Archive exceeded the 8 MiB limit")
    with tempfile.TemporaryDirectory(prefix="movielens-", dir=target.parent) as temporary:
        stage = Path(temporary)
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            # Read only named members; never extract archive-controlled paths.
            for filename in ["movies.csv", "ratings.csv", "README.txt"]:
                member = package.getinfo(f"ml-latest-small/{filename}")
                if member.file_size > 100 * 1024 * 1024:
                    raise ValueError(f"Archive member too large: {filename}")
                (stage / filename).write_bytes(package.read(member))
        load_dataset(stage)
        (stage / "provenance.json").write_text(json.dumps({
            "synthetic": False, "dataset": "MovieLens latest-small",
            "source": DATASET_PAGE, "download_url": ARCHIVE_URL,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "archive_sha256": hashlib.sha256(archive).hexdigest(),
            "terms": "See the original README.txt included with this download.",
            "license_accepted_by_cli_user": True,
        }, indent=2) + "\n", encoding="utf-8")
        target.mkdir(parents=True, exist_ok=True)
        for path in stage.iterdir():
            path.replace(target / path.name)
    return target
