import json

import pytest

from recommendation_engine.cli import main


def test_demo_trains_evaluates_and_recommend_command_uses_saved_artifact(tmp_path, capsys):
    data = tmp_path / "data"
    artifact = tmp_path / "model.joblib"
    report = tmp_path / "report.json"
    main(["generate-demo", "--output", str(data)])
    main(["demo", "--data", str(data), "--model", str(artifact), "--output", str(report)])
    assert artifact.exists()
    assert artifact.with_suffix(".metadata.json").exists()
    assert json.loads(report.read_text())["test_ratings"] == 120
    capsys.readouterr()
    main(["recommend", "--model", str(artifact), "--user-id", "999", "--k", "3"])
    result = json.loads(capsys.readouterr().out)
    assert result["cold_start"]
    assert len(result["recommendations"]) == 3


def test_cli_reports_missing_data_without_traceback(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main(["train", "--data", str(tmp_path / "missing")])
    assert error.value.code == 2
    assert "Error:" in capsys.readouterr().err
