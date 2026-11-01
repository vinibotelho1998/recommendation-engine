import io
import json
import zipfile
from unittest.mock import patch

import pytest

from recommendation_engine.download import download_movielens


def make_archive(dataset, duplicate=False):
    output = io.BytesIO()
    ratings = dataset.ratings
    if duplicate:
        import pandas as pd

        ratings = pd.concat([ratings, ratings.iloc[:1]], ignore_index=True)
    with zipfile.ZipFile(output, "w") as package:
        package.writestr("ml-latest-small/movies.csv", dataset.movies.to_csv(index=False))
        package.writestr("ml-latest-small/ratings.csv", ratings.to_csv(index=False))
        package.writestr("ml-latest-small/README.txt", "Fixture terms; not the real MovieLens license")
        package.writestr("../../unexpected.txt", "must not be extracted")
    return output.getvalue()


def test_downloader_requires_explicit_consent_before_network(tmp_path):
    with patch("urllib.request.urlopen") as request:
        with pytest.raises(ValueError, match="--accept-license"):
            download_movielens(tmp_path / "movielens")
        request.assert_not_called()


def test_downloader_validates_dataset_and_extracts_only_named_members(dataset, tmp_path):
    target = tmp_path / "movielens"
    with patch("urllib.request.urlopen", return_value=io.BytesIO(make_archive(dataset))):
        download_movielens(target, accept_license=True)
    assert {item.name for item in target.iterdir()} == {
        "movies.csv", "ratings.csv", "README.txt", "provenance.json",
    }
    provenance = json.loads((target / "provenance.json").read_text())
    assert provenance["synthetic"] is False
    assert len(provenance["archive_sha256"]) == 64
    assert not (tmp_path / "unexpected.txt").exists()


def test_failed_validation_does_not_install_dataset(dataset, tmp_path):
    target = tmp_path / "movielens"
    with patch("urllib.request.urlopen", return_value=io.BytesIO(make_archive(dataset, duplicate=True))):
        with pytest.raises(ValueError, match="Duplicate"):
            download_movielens(target, accept_license=True)
    assert not target.exists()


def test_existing_dataset_is_not_overwritten(tmp_path):
    target = tmp_path / "movielens"
    target.mkdir()
    (target / "keep.txt").write_text("existing data")
    with patch("urllib.request.urlopen") as request:
        with pytest.raises(ValueError, match="not empty"):
            download_movielens(target, accept_license=True)
        request.assert_not_called()
