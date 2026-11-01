"""Small commands that keep data preparation, evaluation and serving separate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .data import generate_demo, load_dataset
from .download import download_movielens
from .evaluation import evaluate
from .model import Recommender, train


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Train, evaluate and inspect movie recommendations")
    commands = root.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate-demo", help="Regenerate the synthetic fixture")
    generate.add_argument("--output", type=Path, default=Path("data/demo"))
    generate.add_argument("--seed", type=int, default=42)
    for name in ["train", "evaluate", "demo"]:
        command = commands.add_parser(name)
        command.add_argument("--data", type=Path, default=Path("data/demo"))
        command.add_argument("--neighbors", type=int, default=30)
        if name in {"train", "demo"}:
            command.add_argument("--model", type=Path, default=Path("var/model.joblib"))
        if name in {"evaluate", "demo"}:
            command.add_argument("--output", type=Path, default=Path("var/evaluation.json"))
    recommend = commands.add_parser("recommend")
    recommend.add_argument("--model", type=Path, default=Path("var/model.joblib"))
    recommend.add_argument("--user-id", type=int, required=True)
    recommend.add_argument("--k", type=int, default=10)
    download = commands.add_parser("download-movielens")
    download.add_argument("--output", type=Path, default=Path("data/movielens"))
    download.add_argument("--accept-license", action="store_true")
    return root


def main(argv: list[str] | None = None) -> None:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "generate-demo":
            generate_demo(arguments.output, arguments.seed)
            print(f"Synthetic data written to {arguments.output}")
            return
        if arguments.command == "download-movielens":
            path = download_movielens(arguments.output, arguments.accept_license)
            print(f"MovieLens downloaded and validated: {path}")
            return
        if arguments.command == "recommend":
            result = Recommender.load(arguments.model).recommend(arguments.user_id, arguments.k)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return
        dataset = load_dataset(arguments.data)
        if arguments.command in {"evaluate", "demo"}:
            report = evaluate(dataset, neighbors=arguments.neighbors)
            _write_json(arguments.output, report)
            print(f"Evaluation written to {arguments.output}")
            for row in report["results"]:
                print(
                    f"{row['method']:16} k={row['k']:2} "
                    f"precision={row['precision_at_k']:.4f} "
                    f"recall={row['recall_at_k']:.4f} mrr={row['mrr_at_k']:.4f}"
                )
        if arguments.command in {"train", "demo"}:
            model = train(dataset, arguments.neighbors)
            model.save(arguments.model)
            _write_json(arguments.model.with_suffix(".metadata.json"), model.metadata)
            print(f"Serving artifact: {arguments.model} ({model.metadata['version']})")
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
