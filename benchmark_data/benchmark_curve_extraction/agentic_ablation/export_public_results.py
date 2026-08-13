from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parent
DEFAULT_RUNS = BASE / "runs"
DEFAULT_OUTPUT = BASE / "public_results"


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_text_normalized(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_bytes().decode("utf-8-sig")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def replace_nonfinite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, list):
        return [replace_nonfinite(item) for item in value]
    if isinstance(value, dict):
        return {key: replace_nonfinite(item) for key, item in value.items()}
    return value


def sanitize_provider(provider: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "id",
        "name",
        "base_url",
        "env_key",
        "wire_api",
        "requires_openai_auth",
        "isolated_codex_home",
        "local_openai_credentials_inherited",
        "config_sha256",
    )
    cleaned = {key: provider[key] for key in keep if key in provider}
    if "model_preflight" in provider:
        preflight = provider["model_preflight"]
        cleaned["model_preflight"] = {
            key: preflight[key]
            for key in (
                "models_url",
                "authenticated",
                "model_count",
                "requested_model",
                "requested_model_available",
            )
            if key in preflight
        }
    return cleaned


def export_manifests(run_root: Path, output: Path) -> None:
    experiment = load_json(run_root / "experiment_manifest.json")
    experiment.pop("case_source", None)
    experiment.pop("python_executable", None)
    experiment.pop("frozen_code_archive", None)
    experiment["provider"] = sanitize_provider(experiment.get("provider", {}))
    experiment["case_source"] = (
        "../../benchmark_cases/focused_curve_extraction_set_v4_1_fixed"
    )
    experiment["frozen_code_reference"] = "../../../../code_reference/"
    write_json(output / "experiment_manifest.json", experiment)

    replicate = run_root / "monolithic" / "replicate_01"
    run_manifest = load_json(replicate / "run_manifest.json")
    public_run = {
        key: run_manifest[key]
        for key in (
            "schema_version",
            "generated_at",
            "condition",
            "model",
            "reasoning_effort",
            "codex_bypass_sandbox",
            "input_image_attached",
            "codex_cli_version",
            "max_workers",
            "completed",
            "failed",
            "skipped",
        )
        if key in run_manifest
    }
    public_run["provider"] = sanitize_provider(run_manifest.get("provider", {}))
    write_json(output / "single_agent_60_cases" / "run_manifest.json", public_run)

    worker_manifest = load_json(replicate / "worker_manifest.json")
    public_worker = {
        key: worker_manifest[key]
        for key in (
            "schema_version",
            "generated_at",
            "condition",
            "case_count",
            "ground_truth_in_worker_tree",
            "tool_sha256",
        )
        if key in worker_manifest
    }
    public_worker["cases"] = [
        {
            "case_id": item["case_id"],
            "condition": item["condition"],
            "image_sha256": item["image_sha256"],
            "record": f"cases/{item['case_id']}/response.json",
        }
        for item in worker_manifest["cases"]
    ]
    write_json(output / "single_agent_60_cases" / "worker_manifest.json", public_worker)

    summary_path = output / "single_agent_60_cases" / "case_execution_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "case_id",
        "status",
        "reason",
        "elapsed_seconds",
        "model_calls",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "total_tokens",
        "response_valid",
        "overlap_panel_quality",
    )
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in run_manifest["results"]:
            usage = item.get("usage", {})
            postcheck = item.get("postcheck", {})
            writer.writerow(
                {
                    "case_id": item["case_id"],
                    "status": item["status"],
                    "reason": item.get("reason", ""),
                    "elapsed_seconds": item.get("elapsed_seconds", ""),
                    "model_calls": item.get("model_calls", ""),
                    "input_tokens": usage.get("input_tokens", ""),
                    "cached_input_tokens": usage.get("cached_input_tokens", ""),
                    "output_tokens": usage.get("output_tokens", ""),
                    "total_tokens": usage.get("total_tokens", ""),
                    "response_valid": postcheck.get("response_valid", ""),
                    "overlap_panel_quality": postcheck.get(
                        "overlap_panel_quality", ""
                    ),
                }
            )


def export_case_records(run_root: Path, output: Path) -> None:
    replicate = run_root / "monolithic" / "replicate_01"
    cases = sorted(
        path
        for path in replicate.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    )
    if len(cases) != 60:
        raise RuntimeError(f"Expected 60 single-agent cases, found {len(cases)}")

    for case in cases:
        source = case / "monolithic_anchor_extract"
        destination = output / "single_agent_60_cases" / "cases" / case.name
        required = {
            "response.json": source / "response.json",
            "axis_fit_output.json": source / "tmp" / "axis_fit_output.json",
            "curve_overlap_score.json": source / "curve_overlap_score.json",
            "curve_overlay.png": source / "curve_overlay.png",
        }
        missing = [name for name, path in required.items() if not path.exists()]
        if missing:
            raise RuntimeError(f"{case.name} is missing: {', '.join(missing)}")
        for name, path in required.items():
            target = destination / name
            if path.suffix.lower() == ".json":
                write_json(target, replace_nonfinite(load_json(path)))
            else:
                copy_file(path, target)


def export_evaluation(source: Path, destination: Path) -> None:
    allowed = {
        ".csv",
        ".json",
        ".md",
        ".png",
    }
    for path in sorted(source.rglob("*")):
        if path.is_file() and path.suffix.lower() in allowed:
            target = destination / path.relative_to(source)
            if path.suffix.lower() == ".json":
                write_json(target, replace_nonfinite(load_json(path)))
            elif path.suffix.lower() in {".csv", ".md"}:
                copy_text_normalized(path, target)
            else:
                copy_file(path, target)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the completed single-agent benchmark without runtime state."
    )
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    single_run = args.runs_root / "full_single_agent_20260811"
    comparison = (
        args.runs_root
        / "archived_staged_vs_single_agent_rescore_20260811"
        / "evaluation"
        / "replicate_01"
    )
    single_evaluation = single_run / "evaluation" / "replicate_01"
    for required in (single_run, single_evaluation, comparison):
        if not required.exists():
            raise FileNotFoundError(required)

    if args.output.exists():
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)
    copy_text_normalized(
        BASE / "PUBLIC_RESULTS_README.md", args.output / "README.md"
    )

    export_manifests(single_run, args.output)
    export_case_records(single_run, args.output)
    export_evaluation(
        single_evaluation,
        args.output / "single_agent_60_cases" / "evaluation",
    )
    export_evaluation(
        comparison,
        args.output / "retrospective_staged_comparison",
    )

    print(args.output)


if __name__ == "__main__":
    main()
