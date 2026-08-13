#!/usr/bin/env python3
"""Run and evaluate the single-agent versus staged curve benchmark."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
BENCHMARK_ROOT = HERE.parent
DEFAULT_CONFIG_PATH = HERE / "benchmark_config.json"
DEFAULT_CASE_SET = "focused_curve_extraction_set_v4_1_fixed"
DEFAULT_CASE_SOURCE = BENCHMARK_ROOT / "benchmark_cases" / DEFAULT_CASE_SET
DEFAULT_TRUTH_SOURCE = BENCHMARK_ROOT / "peeragent_ground_truth" / DEFAULT_CASE_SET
DEFAULT_CODE_ARCHIVE = REPO_ROOT / "code_reference" / "peeragent_code_dc6189f6bc0a.zip"
DEFAULT_RUN_ROOT = HERE / "runs"
PROMPT_PATH = HERE / "prompts" / "monolithic_anchor_extract.md"
SCHEMA_PATH = HERE / "schemas" / "monolithic_anchor_extract.schema.json"

FORBIDDEN_WORKER_NAMES = (
    "ground_truth",
    "answer",
    "_private_eval",
    "raw.csv",
    "metadata.json",
    "benchmark.html",
)

LOCAL_OPENAI_CREDENTIAL_KEYS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_ORG_ID",
    "OPENAI_ORGANIZATION",
    "OPENAI_PROJECT",
    "CODEX_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_jsonl_first(path: Path) -> dict[str, Any]:
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected a JSON object in {path}")
            return payload
    raise ValueError(f"No records found in {path}")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    return read_json(path)


def provider_settings(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("provider")
    if not isinstance(raw, dict):
        raise ValueError("benchmark_config.json must define a provider object.")
    required = ("id", "name", "base_url", "env_key", "wire_api")
    missing = [key for key in required if not str(raw.get(key, "")).strip()]
    if missing:
        raise ValueError(f"Provider configuration is missing: {', '.join(missing)}")
    forbidden_secret_fields = ("api_key", "token", "bearer_token", "secret")
    present_secrets = [key for key in forbidden_secret_fields if str(raw.get(key, "")).strip()]
    if present_secrets:
        raise ValueError(
            "Provider secrets must not be stored in benchmark_config.json; use env_key only."
        )
    if raw["wire_api"] != "responses":
        raise ValueError("Codex custom providers require wire_api='responses'.")
    if not str(raw["base_url"]).startswith("https://"):
        raise ValueError("Provider base_url must use HTTPS.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", str(raw["id"])):
        raise ValueError("Provider id may contain only letters, digits, underscores, and hyphens.")
    if bool(raw.get("requires_openai_auth", False)):
        raise ValueError("This benchmark requires provider-scoped authentication only.")
    return {
        "id": str(raw["id"]),
        "name": str(raw["name"]),
        "base_url": str(raw["base_url"]),
        "env_key": str(raw["env_key"]),
        "wire_api": str(raw["wire_api"]),
        "requires_openai_auth": bool(raw.get("requires_openai_auth", False)),
    }


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def write_isolated_codex_config(run_root: Path, config: dict[str, Any]) -> tuple[Path, Path]:
    provider = provider_settings(config)
    codex_home = run_root.resolve() / "_codex_provider"
    codex_home.mkdir(parents=True, exist_ok=True)
    auth_path = codex_home / "auth.json"
    if auth_path.exists():
        raise RuntimeError(
            f"Refusing to use an isolated provider home containing auth.json: {auth_path}"
        )
    provider_id = provider["id"]
    config_path = codex_home / "config.toml"
    contents = "\n".join(
        [
            f"model_provider = {toml_string(provider_id)}",
            "",
            f"[model_providers.{provider_id}]",
            f"name = {toml_string(provider['name'])}",
            f"base_url = {toml_string(provider['base_url'])}",
            f"env_key = {toml_string(provider['env_key'])}",
            f"wire_api = {toml_string(provider['wire_api'])}",
            "requires_openai_auth = false",
            "",
        ]
    )
    config_path.write_text(contents, encoding="utf-8", newline="\n")
    return codex_home, config_path


def build_provider_environment(
    config: dict[str, Any],
    run_root: Path,
    *,
    base_environment: dict[str, str] | None = None,
    require_key: bool = True,
) -> tuple[dict[str, str], dict[str, Any]]:
    provider = provider_settings(config)
    environment = dict(os.environ if base_environment is None else base_environment)
    env_key = provider["env_key"]
    local_credential_names = {key.upper() for key in LOCAL_OPENAI_CREDENTIAL_KEYS}
    for key in list(environment):
        if key.upper() in local_credential_names and key.upper() != env_key.upper():
            environment.pop(key, None)
    api_key = environment.get(env_key, "").strip()
    if require_key and not api_key:
        raise RuntimeError(
            f"Set {env_key} in the process environment before running either benchmark arm."
        )
    codex_home, config_path = write_isolated_codex_config(run_root, config)
    environment["CODEX_HOME"] = str(codex_home)
    audit = {
        "id": provider["id"],
        "name": provider["name"],
        "base_url": provider["base_url"],
        "env_key": env_key,
        "wire_api": provider["wire_api"],
        "requires_openai_auth": False,
        "isolated_codex_home": True,
        "local_openai_credentials_inherited": False,
        "api_key_present": bool(api_key),
        "config_path": str(config_path),
        "config_sha256": file_sha256(config_path),
    }
    return environment, audit


def isolate_worker_provider_environment(
    environment: dict[str, str],
    worker_dir: Path,
) -> dict[str, str]:
    """Give each concurrent Codex process an independent writable home."""
    base_home_value = environment.get("CODEX_HOME", "").strip()
    if not base_home_value:
        raise RuntimeError("Provider environment does not define CODEX_HOME.")
    base_home = Path(base_home_value)
    source_config = base_home / "config.toml"
    if not source_config.exists():
        raise FileNotFoundError(f"Missing isolated provider config: {source_config}")

    worker_key = hashlib.sha256(str(worker_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    worker_home = base_home / "workers" / worker_key
    worker_home.mkdir(parents=True, exist_ok=True)
    worker_auth = worker_home / "auth.json"
    if worker_auth.exists():
        raise RuntimeError(
            f"Refusing to use a worker provider home containing auth.json: {worker_auth}"
        )
    shutil.copy2(source_config, worker_home / "config.toml")

    worker_environment = dict(environment)
    worker_environment["CODEX_HOME"] = str(worker_home)
    return worker_environment


def provider_model_preflight(
    config: dict[str, Any],
    environment: dict[str, str],
    requested_model: str,
    *,
    timeout_seconds: float = 60.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    provider = provider_settings(config)
    api_key = environment.get(provider["env_key"], "").strip()
    if not api_key:
        raise RuntimeError(f"Missing provider key in {provider['env_key']}.")
    models_url = provider["base_url"].rstrip("/") + "/models"
    request = urllib.request.Request(
        models_url,
        method="GET",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Provider preflight failed for {models_url}: {type(exc).__name__}: {exc}"
        ) from exc
    model_ids = {
        str(item.get("id", ""))
        for item in payload.get("data", [])
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    if requested_model and requested_model not in model_ids:
        raise RuntimeError(
            f"Requested model {requested_model!r} was not returned by {models_url}."
        )
    return {
        "models_url": models_url,
        "authenticated": True,
        "model_count": len(model_ids),
        "requested_model": requested_model,
        "requested_model_available": requested_model in model_ids,
    }


def resolve_codex_bypass_sandbox(
    cli_value: bool | None,
    config: dict[str, Any],
) -> bool:
    if cli_value is not None:
        return cli_value
    return bool(config.get("codex_bypass_sandbox", False))


def resolve_max_workers(cli_value: int | None, config: dict[str, Any]) -> int:
    value = cli_value if cli_value is not None else int(config.get("max_workers", 1))
    return max(1, value)


def selected_case_ids(case_source: Path, requested: Sequence[str]) -> list[str]:
    index_path = case_source / "case_index.csv"
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = []
    for row in rows:
        case_id = str(row.get("case_id", "")).strip()
        if case_id:
            ids.append(case_id.lower())
    if not ids:
        ids = sorted(
            path.name.lower()
            for path in case_source.iterdir()
            if path.is_dir() and not path.name.startswith("_")
        )
    if requested:
        requested_set = {value.lower() for value in requested}
        missing = sorted(requested_set.difference(ids))
        if missing:
            raise ValueError(f"Unknown case IDs: {', '.join(missing)}")
        ids = [case_id for case_id in ids if case_id in requested_set]
    return ids


def find_case_image(case_dir: Path) -> Path:
    preferred = case_dir / f"{case_dir.name}.png"
    if preferred.exists():
        return preferred
    images = sorted(path for path in case_dir.glob("*.png") if path.is_file())
    if len(images) != 1:
        raise FileNotFoundError(f"Expected one top-level PNG in {case_dir}; found {len(images)}")
    return images[0]


def resolve_codex_cmd(explicit: str = "") -> str:
    candidates = [explicit] if explicit else []
    candidates.extend(["codex.cmd", "codex"])
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise FileNotFoundError("Could not find Codex CLI (`codex.cmd` or `codex`).")


def codex_cli_version(codex_cmd: str) -> str:
    completed = subprocess.run(
        [codex_cmd, "--version"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return (completed.stdout or completed.stderr).strip()


def extract_frozen_code(run_root: Path, code_archive: Path) -> Path:
    code_parent = run_root / "_frozen_code"
    code_root = code_parent / "peeragent"
    if (code_root / "run_pipeline_batch.py").exists():
        return code_root
    if not code_archive.exists():
        raise FileNotFoundError(f"Frozen code archive not found: {code_archive}")
    code_parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(code_archive, "r") as archive:
        archive.extractall(code_parent)
    if not (code_root / "run_pipeline_batch.py").exists():
        raise FileNotFoundError(f"Archive did not contain peeragent/run_pipeline_batch.py: {code_archive}")
    return code_root


def sanitize_task(task: dict[str, Any], image_path: Path) -> dict[str, Any]:
    clean = {
        "task_id": task.get("task_id", ""),
        "task_type": "panel_anchoring",
        "case_id": str(task.get("case_id", "")).lower(),
        "paper_id": task.get("paper_id", ""),
        "paper_title": task.get("paper_title", ""),
        "figure_id": task.get("figure_id", ""),
        "figure_label": task.get("figure_label", ""),
        "image_path": str(image_path.resolve()),
        "panel_id": task.get("panel_id", ""),
        "panel_label": task.get("panel_label", ""),
        "priority": task.get("priority", "high"),
        "figure_caption": task.get("figure_caption", ""),
        "caption_snippet": task.get("caption_snippet", ""),
        "candidate_catalysts": task.get("candidate_catalysts", []),
        "reason": "Single-panel anchoring-and-curve-extraction benchmark.",
        "special_notes": (
            f"{str(task.get('special_notes', '')).strip()} "
            "Use only the supplied PNG and task context. Do not inspect other cases, "
            "existing outputs, raw source data, answer keys, or evaluation files."
        ).strip(),
    }
    return clean


def audit_worker_tree(condition_root: Path) -> list[str]:
    violations: list[str] = []
    for path in condition_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(condition_root).as_posix().lower()
        if any(fragment in relative for fragment in FORBIDDEN_WORKER_NAMES):
            violations.append(relative)
    return violations


def prepare_condition(
    condition: str,
    condition_root: Path,
    case_source: Path,
    case_ids: Sequence[str],
    code_root: Path,
) -> None:
    condition_root.mkdir(parents=True, exist_ok=True)
    tools = ("fit_axis_mapping.py", "score_panel_curve_overlap.py")
    prepared = []
    for case_id in case_ids:
        source_dir = case_source / case_id
        if not source_dir.exists():
            raise FileNotFoundError(f"Missing source case: {source_dir}")
        destination = condition_root / case_id
        destination.mkdir(parents=True, exist_ok=True)

        source_image = find_case_image(source_dir)
        image_path = destination / source_image.name
        shutil.copy2(source_image, image_path)

        source_task_path = source_dir / "codex_orchestrator" / "panel_tasks.jsonl"
        task = sanitize_task(read_jsonl_first(source_task_path), image_path)
        write_json(destination / "task.json", task)
        write_jsonl(destination / "codex_orchestrator" / "panel_tasks.jsonl", [task])

        tool_dir = destination / "tools"
        tool_dir.mkdir(parents=True, exist_ok=True)
        for filename in tools:
            shutil.copy2(code_root / filename, tool_dir / filename)
        prepared.append(
            {
                "case_id": case_id,
                "condition": condition,
                "image": str(image_path.resolve()),
                "image_sha256": file_sha256(image_path),
                "task": str((destination / "task.json").resolve()),
            }
        )

    violations = audit_worker_tree(condition_root)
    if violations:
        raise RuntimeError(
            "Leakage audit failed; forbidden worker files were found:\n"
            + "\n".join(f"- {item}" for item in violations)
        )
    write_json(
        condition_root / "worker_manifest.json",
        {
            "schema_version": "1.0",
            "generated_at": now_iso(),
            "condition": condition,
            "case_count": len(prepared),
            "ground_truth_in_worker_tree": False,
            "tool_sha256": {
                filename: file_sha256(code_root / filename)
                for filename in tools
            },
            "cases": prepared,
        },
    )


def prepare(args: argparse.Namespace, config: dict[str, Any]) -> None:
    run_root = args.run_root.resolve()
    case_source = args.case_source.resolve()
    _, provider_audit = build_provider_environment(
        config,
        run_root,
        require_key=False,
    )
    code_root = extract_frozen_code(run_root, args.code_archive.resolve())
    case_ids = selected_case_ids(case_source, args.case)
    for condition in ("monolithic", "staged"):
        condition_root = run_root / condition / f"replicate_{args.replicate:02d}"
        if condition_root.exists() and any(condition_root.iterdir()):
            if not args.force_prepare:
                raise FileExistsError(
                    f"Prepared workspace already exists: {condition_root}. "
                    "Use a new --replicate/--run-root or pass --force-prepare."
                )
            resolved_root = run_root.resolve()
            resolved_condition = condition_root.resolve()
            if resolved_root not in resolved_condition.parents:
                raise RuntimeError(
                    f"Refusing to reset a directory outside the run root: {resolved_condition}"
                )
            shutil.rmtree(resolved_condition)
        prepare_condition(condition, condition_root, case_source, case_ids, code_root)
    write_json(
        run_root / "experiment_manifest.json",
        {
            "schema_version": "1.0",
            "generated_at": now_iso(),
            "case_source": str(case_source),
            "case_count": len(case_ids),
            "case_ids": case_ids,
            "model": args.model or config.get("model", ""),
            "reasoning_effort": args.reasoning_effort or config.get("reasoning_effort", ""),
            "codex_bypass_sandbox": resolve_codex_bypass_sandbox(
                args.codex_bypass_sandbox, config
            ),
            "attach_input_image": bool(config.get("attach_input_image", True)),
            "python_executable": sys.executable,
            "provider": provider_audit,
            "replicate": args.replicate,
            "frozen_code_archive": str(args.code_archive.resolve()),
            "frozen_code_archive_sha256": file_sha256(args.code_archive.resolve()),
            "monolithic_prompt_sha256": file_sha256(PROMPT_PATH),
            "monolithic_schema_sha256": file_sha256(SCHEMA_PATH),
            "config_sha256": file_sha256(args.config.resolve()),
            "ground_truth_used_during_prepare": False,
        },
    )
    print(f"Prepared {len(case_ids)} cases per condition under {run_root}")


def prompt_for_case(case_dir: Path, task: dict[str, Any]) -> tuple[str, dict[str, Path]]:
    output_dir = case_dir / "monolithic_anchor_extract"
    tmp_dir = output_dir / "tmp"
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    image_path = Path(str(task["image_path"])).resolve()
    paths = {
        "output_dir": output_dir,
        "response": output_dir / "response.json",
        "events": output_dir / "events.jsonl",
        "stderr": output_dir / "stderr.log",
        "saved_panel": output_dir / "panel_image.png",
        "saved_overlay": output_dir / "curve_overlay.png",
        "axis_fit_input": tmp_dir / "axis_fit_input.json",
        "axis_fit_output": tmp_dir / "axis_fit_output.json",
        "curve_candidate": tmp_dir / "curve_candidate.json",
        "overlap_report": output_dir / "curve_overlap_score.json",
        "overlap_overlay": output_dir / "curve_overlap_diagnostic.png",
        "fit_script": case_dir / "tools" / "fit_axis_mapping.py",
        "overlap_scorer": case_dir / "tools" / "score_panel_curve_overlap.py",
        "image": image_path,
    }
    replacements = {
        "[PAPER_ID]": str(task.get("paper_id", "")),
        "[FIGURE_ID]": str(task.get("figure_id", "")),
        "[PANEL_ID]": str(task.get("panel_id", "")),
        "[PANEL_LABEL]": str(task.get("panel_label", "")),
        "[IMAGE_PATH]": str(image_path),
        "[FIGURE_CAPTION]": str(task.get("figure_caption", "")),
        "[CAPTION_SNIPPET]": str(task.get("caption_snippet", "")),
        "[CANDIDATE_CATALYSTS]": json.dumps(task.get("candidate_catalysts", []), ensure_ascii=False),
        "[SPECIAL_NOTES]": str(task.get("special_notes", "")),
        "[SAVED_PANEL_IMAGE_PATH]": str(paths["saved_panel"]),
        "[SAVED_CURVE_OVERLAY_PATH]": str(paths["saved_overlay"]),
        "[AXIS_FIT_INPUT_PATH]": str(paths["axis_fit_input"]),
        "[AXIS_FIT_OUTPUT_PATH]": str(paths["axis_fit_output"]),
        "[CURVE_CANDIDATE_PATH]": str(paths["curve_candidate"]),
        "[OVERLAP_REPORT_PATH]": str(paths["overlap_report"]),
        "[OVERLAP_OVERLAY_PATH]": str(paths["overlap_overlay"]),
        "[PYTHON_EXECUTABLE]": sys.executable,
        "[FIT_AXIS_SCRIPT_PATH]": str(paths["fit_script"]),
        "[OVERLAP_SCORER_PATH]": str(paths["overlap_scorer"]),
    }
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    for key, value in replacements.items():
        prompt = prompt.replace(key, value)
    unresolved = sorted(set(re.findall(r"\[[A-Z][A-Z0-9_]+\]", prompt)))
    if unresolved:
        raise ValueError(f"Unresolved prompt placeholders: {', '.join(unresolved)}")
    return prompt, paths


def recursively_collect_usage(value: Any, collected: dict[str, int]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower()
            if normalized in {
                "input_tokens",
                "output_tokens",
                "cached_input_tokens",
                "total_tokens",
                "reasoning_tokens",
            } and isinstance(item, (int, float)):
                collected[normalized] = max(collected.get(normalized, 0), int(item))
            recursively_collect_usage(item, collected)
    elif isinstance(value, list):
        for item in value:
            recursively_collect_usage(item, collected)


def parse_usage(events_path: Path) -> dict[str, int]:
    usage: dict[str, int] = {}
    if not events_path.exists():
        return usage
    for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            recursively_collect_usage(json.loads(line), usage)
        except json.JSONDecodeError:
            continue
    if "total_tokens" not in usage and ("input_tokens" in usage or "output_tokens" in usage):
        usage["total_tokens"] = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    return usage


def parse_codex_reported_tokens(path: Path) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(r"(?im)^\s*tokens used\s*$\s*^\s*([0-9][0-9,]*)\s*$", text)
    if not matches:
        return 0
    return int(matches[-1].replace(",", ""))


def staged_usage(case_dir: Path) -> dict[str, int]:
    anchoring = sum(
        parse_codex_reported_tokens(path)
        for path in case_dir.glob("codex_panel_anchoring/**/tmp/stderr.log")
    )
    extraction = sum(
        parse_codex_reported_tokens(path)
        for path in case_dir.glob("codex_panel_curve_extraction/**/tmp/stderr.log")
    )
    revisions = sum(
        parse_codex_reported_tokens(path)
        for path in case_dir.glob("codex_panel_curve_extraction/**/tmp/revision_stderr.log")
    )
    usage = {
        "anchoring_total_tokens": anchoring,
        "curve_extraction_total_tokens": extraction,
        "revision_total_tokens": revisions,
        "total_tokens": anchoring + extraction + revisions,
    }
    return usage


def monolithic_curve_candidate(response: dict[str, Any]) -> dict[str, Any]:
    x_axis = response.get("x_axis", {})
    y_axis = response.get("y_axis", {})
    curves = []
    for curve in response.get("curves", []):
        item = dict(curve)
        item.setdefault("overlap_recovery_candidate", False)
        item.setdefault("suspected_gap_notes", "")
        curves.append(item)
    qc = response.get("qc", {})
    return {
        "paper_id": response.get("paper_id", ""),
        "figure_id": response.get("figure_id", ""),
        "panel_id": response.get("panel_id", ""),
        "panel_label": response.get("panel_label", ""),
        "saved_panel_image_path": response.get("saved_panel_image_path", ""),
        "saved_curve_overlay_path": response.get("saved_curve_overlay_path", ""),
        "plot_area_box_cropped": response.get("plot_area_box_cropped", []),
        "x_axis_type": x_axis.get("chosen_model", "unknown"),
        "y_axis_type": y_axis.get("chosen_model", "unknown"),
        "legend_entries": response.get("legend_entries", []),
        "panel_type": response.get("panel_type", ""),
        "overlap_recovery_recommended": any(
            item.get("visible_segment_status") != "complete" for item in curves
        ),
        "overlap_recovery_reason": "",
        "curves": curves,
        "interpretation_notes": response.get("interpretation_notes", ""),
        "qc": {
            "curve_count_estimated_correctly": bool(qc.get("curve_count_estimated_correctly", False)),
            "legend_curve_mapping_complete": qc.get("legend_curve_mapping_complete", "ambiguous"),
            "main_plot_only": "yes",
            "points_cover_visible_extent": qc.get("points_cover_visible_extent", "ambiguous"),
            "manual_review_required": bool(qc.get("manual_review_required", False)),
        },
        "unresolved_ambiguities": response.get("unresolved_ambiguities", []),
    }


def postcheck_monolithic(case_dir: Path, paths: dict[str, Path]) -> dict[str, Any]:
    result: dict[str, Any] = {"response_valid": False, "post_overlap_returncode": None}
    if not paths["response"].exists():
        return result
    response = read_json(paths["response"])
    result["response_valid"] = bool(response.get("curves")) and bool(response.get("x_axis")) and bool(
        response.get("y_axis")
    )
    if not paths["saved_panel"].exists():
        shutil.copy2(paths["image"], paths["saved_panel"])
    candidate = monolithic_curve_candidate(response)
    write_json(paths["curve_candidate"], candidate)
    command = [
        sys.executable,
        str(paths["overlap_scorer"]),
        "--panel-image",
        str(paths["saved_panel"]),
        "--response",
        str(paths["curve_candidate"]),
        "--output",
        str(paths["overlap_report"]),
        "--overlay-output",
        str(paths["overlap_overlay"]),
    ]
    completed = subprocess.run(
        command,
        cwd=case_dir,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    result["post_overlap_returncode"] = completed.returncode
    result["post_overlap_stderr"] = completed.stderr[-2000:]
    if paths["overlap_report"].exists():
        report = read_json(paths["overlap_report"])
        result["overlap_panel_quality"] = report.get("summary", {}).get("panel_quality", "")
    return result


def build_monolithic_command(
    *,
    codex_cmd: str,
    case_dir: Path,
    response_path: Path,
    image_path: Path,
    model: str,
    reasoning_effort: str,
    codex_bypass_sandbox: bool,
    attach_input_image: bool,
) -> list[str]:
    command = [
        codex_cmd,
        "exec",
        "--json",
        "--ephemeral",
        "--output-schema",
        str(SCHEMA_PATH),
        "-o",
        str(response_path),
        "--skip-git-repo-check",
        "--color",
        "never",
        "-C",
        str(case_dir),
    ]
    if codex_bypass_sandbox:
        command.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        command.extend(["--sandbox", "workspace-write"])
    if model:
        command.extend(["-m", model])
    if reasoning_effort:
        command.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    if attach_input_image:
        command.extend(["-i", str(image_path)])
    command.append("-")
    return command


def run_monolithic_case(
    case_dir: Path,
    codex_cmd: str,
    model: str,
    reasoning_effort: str,
    codex_bypass_sandbox: bool,
    attach_input_image: bool,
    provider_environment: dict[str, str],
    rerun: bool,
) -> dict[str, Any]:
    task = read_json(case_dir / "task.json")
    prompt, paths = prompt_for_case(case_dir, task)
    if paths["response"].exists() and not rerun:
        try:
            postcheck = postcheck_monolithic(case_dir, paths)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return {
                "case_id": case_dir.name,
                "status": "failed",
                "reason": f"invalid_existing_response: {type(exc).__name__}: {exc}",
                "response_path": str(paths["response"]),
            }
        return {
            "case_id": case_dir.name,
            "status": "completed" if postcheck.get("response_valid") else "failed",
            "reason": "validated_existing_response",
            "response_path": str(paths["response"]),
            "elapsed_seconds": (
                max(
                    0.0,
                    paths["response"].stat().st_mtime
                    - (paths["output_dir"] / "prompt.md").stat().st_mtime,
                )
                if (paths["output_dir"] / "prompt.md").exists()
                else ""
            ),
            "model_calls": 1,
            "usage": parse_usage(paths["events"]),
            "postcheck": postcheck,
        }
    (paths["output_dir"] / "prompt.md").write_text(prompt, encoding="utf-8")
    command = build_monolithic_command(
        codex_cmd=codex_cmd,
        case_dir=case_dir,
        response_path=paths["response"],
        image_path=paths["image"],
        model=model,
        reasoning_effort=reasoning_effort,
        codex_bypass_sandbox=codex_bypass_sandbox,
        attach_input_image=attach_input_image,
    )
    worker_environment = isolate_worker_provider_environment(provider_environment, case_dir)
    start = time.perf_counter()
    completed = subprocess.run(
        command,
        input=prompt,
        cwd=case_dir,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env=worker_environment,
    )
    elapsed = time.perf_counter() - start
    paths["events"].write_text(completed.stdout, encoding="utf-8")
    paths["stderr"].write_text(completed.stderr, encoding="utf-8")
    postcheck = postcheck_monolithic(case_dir, paths) if completed.returncode == 0 else {}
    return {
        "case_id": case_dir.name,
        "status": "completed" if completed.returncode == 0 and postcheck.get("response_valid") else "failed",
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "model_calls": 1,
        "response_path": str(paths["response"]),
        "usage": parse_usage(paths["events"]),
        "postcheck": postcheck,
    }


def run_monolithic(args: argparse.Namespace, config: dict[str, Any]) -> None:
    condition_root = args.run_root.resolve() / "monolithic" / f"replicate_{args.replicate:02d}"
    if not condition_root.exists():
        raise FileNotFoundError("Run `prepare` before `run-monolithic`.")
    case_ids = selected_case_ids(args.case_source.resolve(), args.case)
    codex_cmd = resolve_codex_cmd(args.codex_cmd)
    model = args.model or str(config.get("model", ""))
    effort = args.reasoning_effort or str(config.get("reasoning_effort", ""))
    bypass = resolve_codex_bypass_sandbox(args.codex_bypass_sandbox, config)
    max_workers = resolve_max_workers(args.max_workers, config)
    attach_input_image = bool(config.get("attach_input_image", True))
    provider_environment, provider_audit = build_provider_environment(
        config,
        args.run_root.resolve(),
    )
    provider_audit["model_preflight"] = provider_model_preflight(
        config,
        provider_environment,
        model,
    )
    results = parallel_cases(
        case_ids,
        max_workers,
        lambda case_id: run_monolithic_case(
            condition_root / case_id,
            codex_cmd,
            model,
            effort,
            bypass,
            attach_input_image,
            provider_environment,
            args.rerun,
        ),
    )
    write_run_manifest(
        condition_root,
        "monolithic",
        model,
        effort,
        bypass,
        attach_input_image,
        provider_audit,
        codex_cli_version(codex_cmd),
        max_workers,
        results,
    )


def run_subprocess_logged(
    command: list[str],
    cwd: Path,
    log_prefix: Path,
    environment: dict[str, str],
) -> tuple[int, float]:
    start = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env=environment,
    )
    elapsed = time.perf_counter() - start
    log_prefix.parent.mkdir(parents=True, exist_ok=True)
    log_prefix.with_suffix(".stdout.log").write_text(completed.stdout, encoding="utf-8")
    log_prefix.with_suffix(".stderr.log").write_text(completed.stderr, encoding="utf-8")
    return completed.returncode, elapsed


def run_staged_case(
    case_dir: Path,
    code_root: Path,
    codex_cmd: str,
    model: str,
    reasoning_effort: str,
    codex_bypass_sandbox: bool,
    provider_environment: dict[str, str],
    rerun: bool,
) -> dict[str, Any]:
    logs = case_dir / "_comparison_logs"
    worker_environment = isolate_worker_provider_environment(provider_environment, case_dir)
    common = ["--codex-cmd", codex_cmd]
    if model:
        common.extend(["--model", model])
    if reasoning_effort:
        common.extend(["--reasoning-effort", reasoning_effort])
    if codex_bypass_sandbox:
        common.append("--codex-bypass-sandbox")
    if rerun:
        common.append("--rerun")
    anchor_command = [
        sys.executable,
        str(code_root / "run_codex_panel_anchoring.py"),
        str(case_dir),
        *common,
    ]
    anchor_code, anchor_elapsed = run_subprocess_logged(
        anchor_command,
        code_root,
        logs / "anchoring",
        worker_environment,
    )
    if anchor_code != 0:
        return {
            "case_id": case_dir.name,
            "status": "failed",
            "failed_stage": "anchoring",
            "returncode": anchor_code,
            "elapsed_seconds": anchor_elapsed,
            "model_calls": 1,
            "usage": staged_usage(case_dir),
        }
    curve_command = [
        sys.executable,
        str(code_root / "run_codex_panel_curve_extraction.py"),
        str(case_dir),
        *common,
    ]
    curve_code, curve_elapsed = run_subprocess_logged(
        curve_command,
        code_root,
        logs / "curve",
        worker_environment,
    )
    revisions = len(list(case_dir.glob("codex_panel_curve_extraction/**/revision_response.json")))
    return {
        "case_id": case_dir.name,
        "status": "completed" if curve_code == 0 else "failed",
        "failed_stage": "" if curve_code == 0 else "curve",
        "returncode": curve_code,
        "elapsed_seconds": anchor_elapsed + curve_elapsed,
        "anchoring_seconds": anchor_elapsed,
        "curve_seconds": curve_elapsed,
        "model_calls": 2 + revisions,
        "extraction_revision_calls": revisions,
        "usage": staged_usage(case_dir),
    }


def run_staged(args: argparse.Namespace, config: dict[str, Any]) -> None:
    run_root = args.run_root.resolve()
    condition_root = run_root / "staged" / f"replicate_{args.replicate:02d}"
    if not condition_root.exists():
        raise FileNotFoundError("Run `prepare` before `run-staged`.")
    code_root = extract_frozen_code(run_root, args.code_archive.resolve())
    case_ids = selected_case_ids(args.case_source.resolve(), args.case)
    codex_cmd = resolve_codex_cmd(args.codex_cmd)
    model = args.model or str(config.get("model", ""))
    effort = args.reasoning_effort or str(config.get("reasoning_effort", ""))
    bypass = resolve_codex_bypass_sandbox(args.codex_bypass_sandbox, config)
    max_workers = resolve_max_workers(args.max_workers, config)
    provider_environment, provider_audit = build_provider_environment(
        config,
        run_root,
    )
    provider_audit["model_preflight"] = provider_model_preflight(
        config,
        provider_environment,
        model,
    )
    results = parallel_cases(
        case_ids,
        max_workers,
        lambda case_id: run_staged_case(
            condition_root / case_id,
            code_root,
            codex_cmd,
            model,
            effort,
            bypass,
            provider_environment,
            args.rerun,
        ),
    )
    write_run_manifest(
        condition_root,
        "staged",
        model,
        effort,
        bypass,
        True,
        provider_audit,
        codex_cli_version(codex_cmd),
        max_workers,
        results,
    )


def parallel_cases(
    case_ids: Sequence[str],
    max_workers: int,
    worker: Callable[[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        futures = {executor.submit(worker, case_id): case_id for case_id in case_ids}
        for future in as_completed(futures):
            case_id = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                result = {
                    "case_id": case_id,
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            results.append(result)
            print(f"{result['case_id']}: {result['status']}")
    return sorted(results, key=lambda item: item["case_id"])


def write_run_manifest(
    condition_root: Path,
    condition: str,
    model: str,
    reasoning_effort: str,
    codex_bypass_sandbox: bool,
    input_image_attached: bool,
    provider_audit: dict[str, Any],
    codex_version: str,
    max_workers: int,
    results: list[dict[str, Any]],
) -> None:
    manifest = {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "condition": condition,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "codex_bypass_sandbox": codex_bypass_sandbox,
        "input_image_attached": input_image_attached,
        "provider": provider_audit,
        "python_executable": sys.executable,
        "codex_cli_version": codex_version,
        "max_workers": max_workers,
        "completed": sum(item.get("status") == "completed" for item in results),
        "failed": sum(item.get("status") == "failed" for item in results),
        "skipped": sum(item.get("status") == "skipped" for item in results),
        "results": results,
    }
    write_json(condition_root / "run_manifest.json", manifest)
    print(
        f"{condition}: completed={manifest['completed']} "
        f"failed={manifest['failed']} skipped={manifest['skipped']}"
    )


def normalize_label(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.replace("−", "-").replace("–", "-")
    value = re.sub(r"\\mathrm|\\text|\\mathbf", "", value)
    value = value.replace("$", "").replace("{", "").replace("}", "")
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def parse_number(value: Any) -> float:
    text = str(value).strip()
    text = text.replace("−", "-").replace("–", "-").replace(",", "")
    text = text.replace("×", "x")
    direct = re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text)
    if direct:
        return float(text)
    bare_power = re.fullmatch(r"10\s*(?:\^|\*\*)\s*\{?\s*([+-]?\d+)\s*\}?", text)
    if bare_power:
        return 10.0 ** int(bare_power.group(1))
    power = re.fullmatch(
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*x\s*10\s*\^?\s*([+-]?\d+)",
        text,
    )
    if power:
        return float(power.group(1)) * (10.0 ** int(power.group(2)))
    raise ValueError(f"Not a numeric tick value: {value!r}")


@dataclass
class AxisFit:
    model: str
    slope: float
    intercept: float
    rmse: float
    anchor_count: int

    def value(self, pixel: float) -> float:
        transformed = self.slope * pixel + self.intercept
        if self.model == "log10":
            return 10.0**transformed
        return transformed


def linear_fit(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float, float]:
    if len(xs) < 2 or len(set(xs)) < 2:
        raise ValueError("At least two distinct pixel anchors are required.")
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    intercept = y_mean - slope * x_mean
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    rmse = math.sqrt(statistics.fmean(value * value for value in residuals))
    return slope, intercept, rmse


def fit_axis(
    anchors: Sequence[dict[str, Any]],
    axis: str,
    model: str,
    crop_box: Sequence[float],
) -> AxisFit:
    pixels: list[float] = []
    values: list[float] = []
    for anchor in anchors:
        try:
            value = parse_number(anchor.get("tick_value", ""))
        except ValueError:
            continue
        pixel = float(anchor["pixel_x"] if axis == "x" else anchor["pixel_y"])
        if anchor.get("coordinate_system") == "cropped_panel":
            pixel += float(crop_box[0] if axis == "x" else crop_box[1])
        pixels.append(pixel)
        values.append(value)
    normalized_model = "log10" if "log" in model.lower() else "linear"
    if normalized_model == "log10":
        if any(value <= 0 for value in values):
            raise ValueError("Log10 axis has non-positive tick anchors.")
        target = [math.log10(value) for value in values]
    else:
        target = values
    slope, intercept, rmse = linear_fit(pixels, target)
    return AxisFit(normalized_model, slope, intercept, rmse, len(pixels))


def first_matching_response(case_dir: Path, pattern: str) -> Path:
    matches = sorted(case_dir.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No response matched {pattern} in {case_dir}")
    return matches[0]


def load_condition_record(condition: str, case_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if condition == "monolithic":
        response = read_json(case_dir / "monolithic_anchor_extract" / "response.json")
        x_axis = response.get("x_axis", {})
        y_axis = response.get("y_axis", {})
        anchors = []
        for axis_name, axis_payload in (("x", x_axis), ("y", y_axis)):
            for anchor in axis_payload.get("anchors", []):
                item = dict(anchor)
                item["axis"] = axis_name
                anchors.append(item)
        anchor_response = {
            "crop_box_original": response.get("crop_box_original", [0, 0, 0, 0]),
            "anchor_points": anchors,
            "axis_mapping": {
                "x": {"chosen_model": x_axis.get("chosen_model", "unknown")},
                "y": {"chosen_model": y_axis.get("chosen_model", "unknown")},
            },
        }
        return anchor_response, monolithic_curve_candidate(response)
    anchor_path = first_matching_response(
        case_dir, "codex_panel_anchoring/panel_runs/*/response.json"
    )
    curve_path = first_matching_response(
        case_dir, "codex_panel_curve_extraction/panel_runs/*/response.json"
    )
    return read_json(anchor_path), read_json(curve_path)


def scientific_curves(
    anchor_response: dict[str, Any],
    curve_response: dict[str, Any],
) -> tuple[list[dict[str, Any]], AxisFit, AxisFit]:
    crop_box = anchor_response.get("crop_box_original", [0, 0, 0, 0])
    if len(crop_box) != 4:
        raise ValueError("Invalid crop_box_original.")
    anchors = anchor_response.get("anchor_points", [])
    axis_mapping = anchor_response.get("axis_mapping", {})
    x_model = str(axis_mapping.get("x", {}).get("chosen_model", "unknown"))
    y_model = str(axis_mapping.get("y", {}).get("chosen_model", "unknown"))
    x_fit = fit_axis(
        [item for item in anchors if item.get("axis") == "x"], "x", x_model, crop_box
    )
    y_fit = fit_axis(
        [item for item in anchors if item.get("axis") == "y"], "y", y_model, crop_box
    )
    curves = []
    for curve in curve_response.get("curves", []):
        points = []
        for point in curve.get("sampled_points", []):
            pixel_x = float(point["pixel_x"]) + float(crop_box[0])
            pixel_y = float(point["pixel_y"]) + float(crop_box[1])
            try:
                x_value = x_fit.value(pixel_x)
                y_value = y_fit.value(pixel_y)
            except (OverflowError, ValueError):
                continue
            if math.isfinite(x_value) and math.isfinite(y_value):
                points.append((x_value, y_value))
        curves.append(
            {
                "curve_id": curve.get("curve_id", ""),
                "curve_label": curve.get("curve_label", ""),
                "points": points,
                "usable": curve.get("usable_for_normalization", "ambiguous"),
            }
        )
    return curves, x_fit, y_fit


def load_truth_case(
    truth_root: Path,
    truth_index: dict[str, dict[str, str]],
    case_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    row = truth_index[case_id]
    metadata = read_json(truth_root / row["metadata_file"])
    raw_path = truth_root / row["raw_data_file"]
    with raw_path.open("r", encoding="utf-8-sig", newline="") as handle:
        raw_rows = list(csv.DictReader(handle))
    x_column = metadata["x_column"]
    y_column = metadata["y_column"]
    series_column = metadata["series_column"]
    grouped: dict[str, list[tuple[float, float]]] = {}
    for raw in raw_rows:
        grouped.setdefault(raw[series_column], []).append(
            (float(raw[x_column]), float(raw[y_column]))
        )
    curves = [
        {"series": label, "points": sorted(points)}
        for label, points in grouped.items()
    ]
    return str(metadata.get("curve_family", row.get("curve_family", ""))), curves


def truth_index_by_case(truth_root: Path) -> dict[str, dict[str, str]]:
    with (truth_root / "case_truth_index.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        return {
            str(row["case_id"]).lower(): row
            for row in csv.DictReader(handle)
        }


def scaled_points(
    points: Sequence[tuple[float, float]],
    bounds: tuple[float, float, float, float],
) -> list[tuple[float, float]]:
    x_min, x_max, y_min, y_max = bounds
    x_span = max(abs(x_max - x_min), 1e-12)
    y_span = max(abs(y_max - y_min), 1e-12)
    return [((x - x_min) / x_span, (y - y_min) / y_span) for x, y in points]


def display_axis_value(value: float, model: str) -> float:
    if model == "log10":
        if value <= 0:
            raise ValueError("A log10 display axis received a non-positive value.")
        return math.log10(value)
    return value


def display_points(
    points: Sequence[tuple[float, float]],
    x_model: str,
    y_model: str,
) -> list[tuple[float, float]]:
    transformed = []
    for x_value, y_value in points:
        try:
            x_display = display_axis_value(x_value, x_model)
            y_display = display_axis_value(y_value, y_model)
        except ValueError:
            continue
        if math.isfinite(x_display) and math.isfinite(y_display):
            transformed.append((x_display, y_display))
    return transformed


def point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx = bx - ax
    dy = by - ay
    denominator = dx * dx + dy * dy
    if denominator <= 1e-20:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denominator))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distances_to_polyline(
    points: Sequence[tuple[float, float]],
    polyline: Sequence[tuple[float, float]],
) -> list[float]:
    if not points or not polyline:
        return [math.inf]
    if len(polyline) == 1:
        return [math.dist(point, polyline[0]) for point in points]
    segments = list(zip(polyline, polyline[1:]))
    return [
        min(point_segment_distance(point, start, end) for start, end in segments)
        for point in points
    ]


def percentile(values: Sequence[float], probability: float) -> float:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return math.inf
    if len(finite) == 1:
        return finite[0]
    position = probability * (len(finite) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return finite[lower]
    weight = position - lower
    return finite[lower] * (1.0 - weight) + finite[upper] * weight


def pair_metrics(
    predicted: dict[str, Any],
    truth: dict[str, Any],
    bounds: tuple[float, float, float, float],
) -> dict[str, float]:
    predicted_points = scaled_points(predicted["points"], bounds)
    truth_points = scaled_points(truth["points"], bounds)
    forward = distances_to_polyline(predicted_points, truth_points)
    reverse = distances_to_polyline(truth_points, predicted_points)
    symmetric = forward + reverse
    truth_x = [point[0] for point in truth["points"]]
    predicted_x = [point[0] for point in predicted["points"]]
    if truth_x and predicted_x:
        truth_span = max(truth_x) - min(truth_x)
        shared = max(
            0.0,
            min(max(truth_x), max(predicted_x)) - max(min(truth_x), min(predicted_x)),
        )
        coverage = shared / truth_span if truth_span > 0 else 1.0
    else:
        coverage = 0.0
    median_distance = statistics.median(symmetric) if symmetric else math.inf
    p95_distance = percentile(symmetric, 0.95)
    return {
        "median_scaled_distance": median_distance,
        "p95_scaled_distance": p95_distance,
        "mean_scaled_distance": statistics.fmean(symmetric) if symmetric else math.inf,
        "x_coverage": coverage,
        "assignment_cost": median_distance + 0.25 * p95_distance + 0.10 * (1.0 - coverage),
    }


def best_assignment(costs: list[list[float]]) -> list[tuple[int, int]]:
    predicted_count = len(costs)
    truth_count = len(costs[0]) if costs else 0
    if not predicted_count or not truth_count:
        return []
    best: tuple[float, list[tuple[int, int]]] | None = None
    if predicted_count <= truth_count:
        for truth_indices in itertools.permutations(range(truth_count), predicted_count):
            pairs = list(enumerate(truth_indices))
            score = sum(costs[predicted][truth] for predicted, truth in pairs)
            if best is None or score < best[0]:
                best = (score, pairs)
    else:
        for predicted_indices in itertools.permutations(range(predicted_count), truth_count):
            pairs = [(predicted, truth) for truth, predicted in enumerate(predicted_indices)]
            score = sum(costs[predicted][truth] for predicted, truth in pairs)
            if best is None or score < best[0]:
                best = (score, pairs)
    return best[1] if best else []


def format_csv_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value


def write_csv(path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: format_csv_value(row.get(key, "")) for key in columns})


def evaluate_case(
    condition: str,
    case_id: str,
    case_dir: Path,
    truth_root: Path,
    truth_index: dict[str, dict[str, str]],
    thresholds: dict[str, float],
    display_axis_models: tuple[str, str] = ("linear", "linear"),
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    family, truth_curves = load_truth_case(truth_root, truth_index, case_id)
    anchor_response, curve_response = load_condition_record(condition, case_dir)
    predicted_curves, x_fit, y_fit = scientific_curves(anchor_response, curve_response)
    x_display_model, y_display_model = display_axis_models
    for curve in predicted_curves:
        curve["points"] = display_points(
            curve["points"], x_display_model, y_display_model
        )
    for curve in truth_curves:
        curve["points"] = display_points(
            curve["points"], x_display_model, y_display_model
        )
    all_truth_points = [
        point for curve in truth_curves for point in curve["points"]
    ]
    x_values = [point[0] for point in all_truth_points]
    y_values = [point[1] for point in all_truth_points]
    bounds = (min(x_values), max(x_values), min(y_values), max(y_values))
    pair_results = [
        [pair_metrics(predicted, truth, bounds) for truth in truth_curves]
        for predicted in predicted_curves
    ]
    costs = [
        [metrics["assignment_cost"] for metrics in row]
        for row in pair_results
    ]
    assignment = best_assignment(costs)
    assigned_predicted = {predicted for predicted, _ in assignment}
    assigned_truth = {truth for _, truth in assignment}
    curve_rows: list[dict[str, Any]] = []
    for predicted_index, truth_index_value in assignment:
        predicted = predicted_curves[predicted_index]
        truth = truth_curves[truth_index_value]
        metrics = pair_results[predicted_index][truth_index_value]
        identity_exact = normalize_label(predicted["curve_label"]) == normalize_label(truth["series"])
        passed = (
            metrics["median_scaled_distance"]
            <= float(thresholds["curve_median_scaled_distance_max"])
            and metrics["p95_scaled_distance"]
            <= float(thresholds["curve_p95_scaled_distance_max"])
            and metrics["x_coverage"] >= float(thresholds["x_coverage_min"])
        )
        curve_rows.append(
            {
                "condition": condition,
                "case_id": case_id,
                "family": family,
                "predicted_curve_id": predicted["curve_id"],
                "predicted_label": predicted["curve_label"],
                "truth_label": truth["series"],
                "identity_exact": identity_exact,
                "predicted_usable": predicted["usable"],
                "n_predicted_points": len(predicted["points"]),
                **metrics,
                "curve_pass": passed,
            }
        )
    for predicted_index, predicted in enumerate(predicted_curves):
        if predicted_index not in assigned_predicted:
            curve_rows.append(
                {
                    "condition": condition,
                    "case_id": case_id,
                    "family": family,
                    "predicted_curve_id": predicted["curve_id"],
                    "predicted_label": predicted["curve_label"],
                    "truth_label": "",
                    "identity_exact": False,
                    "predicted_usable": predicted["usable"],
                    "n_predicted_points": len(predicted["points"]),
                    "curve_pass": False,
                    "assignment_status": "extra_prediction",
                }
            )
    for truth_index_value, truth in enumerate(truth_curves):
        if truth_index_value not in assigned_truth:
            curve_rows.append(
                {
                    "condition": condition,
                    "case_id": case_id,
                    "family": family,
                    "predicted_curve_id": "",
                    "predicted_label": "",
                    "truth_label": truth["series"],
                    "identity_exact": False,
                    "predicted_usable": "",
                    "n_predicted_points": 0,
                    "curve_pass": False,
                    "assignment_status": "missing_prediction",
                }
            )
    matched_rows = [row for row in curve_rows if row.get("truth_label") and row.get("predicted_curve_id")]
    finite_medians = [
        float(row["median_scaled_distance"])
        for row in matched_rows
        if row.get("median_scaled_distance") not in ("", None)
    ]
    finite_p95 = [
        float(row["p95_scaled_distance"])
        for row in matched_rows
        if row.get("p95_scaled_distance") not in ("", None)
    ]
    case_geometry_complete = (
        len(predicted_curves) == len(truth_curves)
        and len(matched_rows) == len(truth_curves)
        and all(bool(row.get("curve_pass")) for row in matched_rows)
    )
    case_complete = (
        case_geometry_complete
        and all(bool(row.get("identity_exact")) for row in matched_rows)
    )
    case_row = {
        "condition": condition,
        "case_id": case_id,
        "family": family,
        "valid_axis_fit": True,
        "x_axis_model": x_fit.model,
        "y_axis_model": y_fit.model,
        "truth_x_display_model": x_display_model,
        "truth_y_display_model": y_display_model,
        "x_anchor_count": x_fit.anchor_count,
        "y_anchor_count": y_fit.anchor_count,
        "x_anchor_fit_rmse": x_fit.rmse,
        "y_anchor_fit_rmse": y_fit.rmse,
        "predicted_curve_count": len(predicted_curves),
        "truth_curve_count": len(truth_curves),
        "curve_count_correct": len(predicted_curves) == len(truth_curves),
        "identity_exact_count": sum(bool(row.get("identity_exact")) for row in matched_rows),
        "matched_curve_count": len(matched_rows),
        "case_median_symmetric_scaled_distance": (
            statistics.median(finite_medians) if finite_medians else math.inf
        ),
        "case_p95_symmetric_scaled_distance": max(finite_p95) if finite_p95 else math.inf,
        "case_geometry_complete_pass": case_geometry_complete,
        "case_complete_pass": case_complete,
    }
    return case_row, curve_rows


def truth_display_models(
    axis_config: dict[str, Any],
    case_id: str,
) -> tuple[str, str]:
    default = axis_config.get("default", {})
    override = axis_config.get("overrides", {}).get(case_id, {})
    return (
        str(override.get("x", default.get("x", "linear"))),
        str(override.get("y", default.get("y", "linear"))),
    )


def overlap_quality(condition: str, case_dir: Path) -> str:
    path: Path | None
    if condition == "monolithic":
        path = case_dir / "monolithic_anchor_extract" / "curve_overlap_score.json"
    else:
        matches = sorted(
            case_dir.glob(
                "codex_panel_curve_extraction/panel_runs/*/curve_overlap_score.json"
            )
        )
        path = matches[0] if matches else None
    if path is None or not path.exists():
        return ""
    payload = read_json(path)
    return str(payload.get("summary", {}).get("panel_quality", ""))


def run_result_index(condition_root: Path) -> dict[str, dict[str, Any]]:
    manifest_path = condition_root / "run_manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = read_json(manifest_path)
    return {
        str(item.get("case_id", "")).lower(): item
        for item in manifest.get("results", [])
        if item.get("case_id")
    }


def summarize_conditions(case_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for condition in sorted({str(row["condition"]) for row in case_rows}):
        subset = [row for row in case_rows if row["condition"] == condition]
        medians = [
            float(row["case_median_symmetric_scaled_distance"])
            for row in subset
            if math.isfinite(float(row["case_median_symmetric_scaled_distance"]))
        ]
        summaries.append(
            {
                "condition": condition,
                "cases": len(subset),
                "valid_axis_fit_cases": sum(bool(row.get("valid_axis_fit")) for row in subset),
                "curve_count_correct_cases": sum(bool(row.get("curve_count_correct")) for row in subset),
                "geometry_complete_pass_cases": sum(
                    bool(row.get("case_geometry_complete_pass")) for row in subset
                ),
                "complete_pass_cases": sum(bool(row.get("case_complete_pass")) for row in subset),
                "median_case_scaled_distance": statistics.median(medians) if medians else math.inf,
                "mean_case_scaled_distance": statistics.fmean(medians) if medians else math.inf,
                "median_elapsed_seconds": (
                    statistics.median(
                        float(row["elapsed_seconds"])
                        for row in subset
                        if row.get("elapsed_seconds") not in ("", None)
                    )
                    if any(row.get("elapsed_seconds") not in ("", None) for row in subset)
                    else math.inf
                ),
                "total_model_calls": sum(
                    int(row.get("model_calls", 0) or 0) for row in subset
                ),
            }
        )
    return summaries


def summarize_families(case_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    keys = sorted(
        {(str(row["condition"]), str(row["family"])) for row in case_rows}
    )
    for condition, family in keys:
        subset = [
            row
            for row in case_rows
            if row["condition"] == condition and row["family"] == family
        ]
        distances = [
            float(row["case_median_symmetric_scaled_distance"])
            for row in subset
            if math.isfinite(float(row["case_median_symmetric_scaled_distance"]))
        ]
        rows.append(
            {
                "condition": condition,
                "family": family,
                "cases": len(subset),
                "geometry_complete_pass_cases": sum(
                    bool(row.get("case_geometry_complete_pass")) for row in subset
                ),
                "complete_pass_cases": sum(
                    bool(row.get("case_complete_pass")) for row in subset
                ),
                "curve_count_correct_cases": sum(
                    bool(row.get("curve_count_correct")) for row in subset
                ),
                "median_case_scaled_distance": (
                    statistics.median(distances) if distances else math.inf
                ),
            }
        )
    return rows


def summarize_curves(
    case_rows: Sequence[dict[str, Any]],
    curve_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for condition in sorted({str(row["condition"]) for row in case_rows}):
        case_subset = [row for row in case_rows if row["condition"] == condition]
        curve_subset = [row for row in curve_rows if row["condition"] == condition]
        matched = [
            row
            for row in curve_subset
            if row.get("truth_label") and row.get("predicted_curve_id")
        ]
        distances = [
            float(row["median_scaled_distance"])
            for row in matched
            if row.get("median_scaled_distance") not in ("", None)
        ]
        rows.append(
            {
                "condition": condition,
                "truth_curves": sum(int(row.get("truth_curve_count", 0)) for row in case_subset),
                "predicted_curves": sum(
                    int(row.get("predicted_curve_count", 0)) for row in case_subset
                ),
                "matched_curves": len(matched),
                "geometry_pass_curves": sum(
                    bool(row.get("curve_pass")) for row in curve_subset
                ),
                "identity_exact_curves": sum(
                    bool(row.get("identity_exact")) for row in curve_subset
                ),
                "median_curve_scaled_distance": (
                    statistics.median(distances) if distances else math.inf
                ),
            }
        )
    return rows


def paired_differences(case_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {
        (str(row["condition"]), str(row["case_id"])): row
        for row in case_rows
    }
    case_ids = sorted(
        {case_id for condition, case_id in indexed if condition == "monolithic"}
        & {case_id for condition, case_id in indexed if condition == "staged"}
    )
    rows = []
    for case_id in case_ids:
        monolithic = indexed[("monolithic", case_id)]
        staged = indexed[("staged", case_id)]
        mono_value = float(monolithic["case_median_symmetric_scaled_distance"])
        staged_value = float(staged["case_median_symmetric_scaled_distance"])
        rows.append(
            {
                "case_id": case_id,
                "family": monolithic["family"],
                "monolithic_case_median_scaled_distance": mono_value,
                "staged_case_median_scaled_distance": staged_value,
                "staged_minus_monolithic": staged_value - mono_value,
                "staged_better": staged_value < mono_value,
                "monolithic_complete_pass": monolithic["case_complete_pass"],
                "staged_complete_pass": staged["case_complete_pass"],
            }
        )
    return rows


def exact_sign_test(differences: Sequence[float]) -> tuple[int, int, int, float]:
    negatives = sum(value < 0 for value in differences)
    positives = sum(value > 0 for value in differences)
    ties = len(differences) - negatives - positives
    n = negatives + positives
    if n == 0:
        return negatives, positives, ties, 1.0
    tail = min(negatives, positives)
    probability = 2.0 * sum(math.comb(n, k) for k in range(tail + 1)) / (2.0**n)
    return negatives, positives, ties, min(1.0, probability)


def bootstrap_median_interval(
    values: Sequence[float],
    replicates: int,
    confidence: float,
    seed: int,
) -> tuple[float, float]:
    if not values:
        return math.nan, math.nan
    generator = random.Random(seed)
    n = len(values)
    medians = []
    for _ in range(replicates):
        sample = [values[generator.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))
    alpha = (1.0 - confidence) / 2.0
    return percentile(medians, alpha), percentile(medians, 1.0 - alpha)


def paired_statistics(
    paired: Sequence[dict[str, Any]],
    statistical_config: dict[str, Any],
) -> dict[str, Any]:
    differences = [float(row["staged_minus_monolithic"]) for row in paired]
    negatives, positives, ties, p_value = exact_sign_test(differences)
    confidence = float(statistical_config.get("bootstrap_confidence_interval", 0.95))
    lower, upper = bootstrap_median_interval(
        differences,
        int(statistical_config.get("bootstrap_replicates", 10000)),
        confidence,
        int(statistical_config.get("random_seed", 20260723)),
    )
    return {
        "paired_cases": len(differences),
        "median_staged_minus_monolithic": (
            statistics.median(differences) if differences else math.nan
        ),
        "bootstrap_confidence": confidence,
        "bootstrap_ci_lower": lower,
        "bootstrap_ci_upper": upper,
        "staged_better_cases": negatives,
        "monolithic_better_cases": positives,
        "ties": ties,
        "exact_sign_test_two_sided_p": p_value,
    }


def evaluation_markdown(
    summaries: Sequence[dict[str, Any]],
    family_summaries: Sequence[dict[str, Any]],
    curve_summaries: Sequence[dict[str, Any]],
    paired: Sequence[dict[str, Any]],
    paired_stats: dict[str, Any],
    errors: Sequence[dict[str, str]],
) -> str:
    evaluated_conditions = {str(row["condition"]) for row in summaries}
    title = (
        "# Single-Agent Evaluation"
        if evaluated_conditions == {"monolithic"}
        else "# Single-Agent Versus Staged Evaluation"
    )
    lines = [
        title,
        "",
        "The evaluator loaded answer curves only after inference. Distances are",
        "computed after each condition's predicted anchors transform pixels into",
        "scientific coordinates, with each case scaled to its answer-curve span.",
        "",
        "## Condition Summary",
        "",
        "| condition | cases | geometry-complete | strict complete | curve-count correct | median scaled distance |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summaries:
        lines.append(
            f"| {row['condition']} | {row['cases']} | "
            f"{row['geometry_complete_pass_cases']} | {row['complete_pass_cases']} | "
            f"{row['curve_count_correct_cases']} | {float(row['median_case_scaled_distance']):.5f} |"
        )
    lines.extend(
        [
            "",
            "## Curve Summary",
            "",
            "| condition | truth curves | predicted curves | geometry pass | exact label identity | median scaled distance |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in curve_summaries:
        lines.append(
            f"| {row['condition']} | {row['truth_curves']} | {row['predicted_curves']} | "
            f"{row['geometry_pass_curves']} | {row['identity_exact_curves']} | "
            f"{float(row['median_curve_scaled_distance']):.5f} |"
        )
    lines.extend(
        [
            "",
            "## Family Summary",
            "",
            "| condition | family | cases | geometry-complete | strict complete | median scaled distance |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in family_summaries:
        lines.append(
            f"| {row['condition']} | {row['family']} | {row['cases']} | "
            f"{row['geometry_complete_pass_cases']} | {row['complete_pass_cases']} | "
            f"{float(row['median_case_scaled_distance']):.5f} |"
        )
    if paired:
        lines.extend(
            [
                "",
                "## Paired Comparison",
                "",
                f"- paired cases: `{len(paired)}`",
                f"- staged better / monolithic better / ties: "
                f"`{paired_stats['staged_better_cases']} / "
                f"{paired_stats['monolithic_better_cases']} / {paired_stats['ties']}`",
                f"- median staged-minus-monolithic distance: "
                f"`{float(paired_stats['median_staged_minus_monolithic']):.5f}`",
                f"- {100 * float(paired_stats['bootstrap_confidence']):.0f}% bootstrap CI: "
                f"`[{float(paired_stats['bootstrap_ci_lower']):.5f}, "
                f"{float(paired_stats['bootstrap_ci_upper']):.5f}]`",
                f"- two-sided exact sign-test p: "
                f"`{float(paired_stats['exact_sign_test_two_sided_p']):.5g}`",
                "",
                "Negative differences favor the staged workflow.",
            ]
        )
    if errors:
        lines.extend(["", "## Evaluation Errors", ""])
        for error in errors:
            lines.append(
                f"- `{error['condition']}` / `{error['case_id']}`: {error['error']}"
            )
    lines.append("")
    return "\n".join(lines)


def evaluate(args: argparse.Namespace, config: dict[str, Any]) -> None:
    run_root = args.run_root.resolve()
    truth_root = args.truth_source.resolve()
    truth_index = truth_index_by_case(truth_root)
    thresholds = config["secondary_thresholds"]
    requested = selected_case_ids(args.case_source.resolve(), args.case)
    invalid_penalty = float(config.get("invalid_record_distance_penalty", 2.0))
    truth_axis_config = config.get("truth_display_axis_models", {})
    case_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    conditions = tuple(dict.fromkeys(args.condition or ("monolithic", "staged")))
    for condition in conditions:
        condition_root = run_root / condition / f"replicate_{args.replicate:02d}"
        run_results = run_result_index(condition_root)
        for case_id in requested:
            case_dir = condition_root / case_id
            try:
                case_row, case_curve_rows = evaluate_case(
                    condition,
                    case_id,
                    case_dir,
                    truth_root,
                    truth_index,
                    thresholds,
                    truth_display_models(truth_axis_config, case_id),
                )
            except Exception as exc:  # noqa: BLE001
                family = ""
                truth_count = 0
                try:
                    family, truth_curves = load_truth_case(
                        truth_root, truth_index, case_id
                    )
                    truth_count = len(truth_curves)
                except Exception:  # noqa: BLE001
                    pass
                run_result = run_results.get(case_id, {})
                case_rows.append(
                    {
                        "condition": condition,
                        "case_id": case_id,
                        "family": family,
                        "valid_axis_fit": False,
                        "x_axis_model": "",
                        "y_axis_model": "",
                        "truth_x_display_model": truth_display_models(
                            truth_axis_config, case_id
                        )[0],
                        "truth_y_display_model": truth_display_models(
                            truth_axis_config, case_id
                        )[1],
                        "x_anchor_count": 0,
                        "y_anchor_count": 0,
                        "x_anchor_fit_rmse": "",
                        "y_anchor_fit_rmse": "",
                        "predicted_curve_count": 0,
                        "truth_curve_count": truth_count,
                        "curve_count_correct": False,
                        "identity_exact_count": 0,
                        "matched_curve_count": 0,
                        "case_median_symmetric_scaled_distance": invalid_penalty,
                        "case_p95_symmetric_scaled_distance": invalid_penalty,
                        "case_geometry_complete_pass": False,
                        "case_complete_pass": False,
                        "overlap_panel_quality": "",
                        "elapsed_seconds": run_result.get("elapsed_seconds", ""),
                        "model_calls": run_result.get("model_calls", ""),
                        "input_tokens": "",
                        "output_tokens": "",
                        "total_tokens": "",
                        "evaluation_error": f"{type(exc).__name__}: {exc}",
                    }
                )
                errors.append(
                    {
                        "condition": condition,
                        "case_id": case_id,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            run_result = run_results.get(case_id, {})
            case_row["overlap_panel_quality"] = overlap_quality(condition, case_dir)
            case_row["elapsed_seconds"] = run_result.get("elapsed_seconds", "")
            case_row["model_calls"] = run_result.get("model_calls", "")
            usage = run_result.get("usage", {})
            case_row["input_tokens"] = usage.get("input_tokens", "")
            case_row["output_tokens"] = usage.get("output_tokens", "")
            case_row["total_tokens"] = usage.get("total_tokens", "")
            case_rows.append(case_row)
            curve_rows.extend(case_curve_rows)
    output_dir = run_root / "evaluation" / f"replicate_{args.replicate:02d}"
    case_columns = [
        "condition",
        "case_id",
        "family",
        "valid_axis_fit",
        "x_axis_model",
        "y_axis_model",
        "truth_x_display_model",
        "truth_y_display_model",
        "x_anchor_count",
        "y_anchor_count",
        "x_anchor_fit_rmse",
        "y_anchor_fit_rmse",
        "predicted_curve_count",
        "truth_curve_count",
        "curve_count_correct",
        "identity_exact_count",
        "matched_curve_count",
        "case_median_symmetric_scaled_distance",
        "case_p95_symmetric_scaled_distance",
        "case_geometry_complete_pass",
        "case_complete_pass",
        "overlap_panel_quality",
        "elapsed_seconds",
        "model_calls",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "evaluation_error",
    ]
    curve_columns = [
        "condition",
        "case_id",
        "family",
        "predicted_curve_id",
        "predicted_label",
        "truth_label",
        "identity_exact",
        "predicted_usable",
        "n_predicted_points",
        "median_scaled_distance",
        "p95_scaled_distance",
        "mean_scaled_distance",
        "x_coverage",
        "assignment_cost",
        "curve_pass",
        "assignment_status",
    ]
    summaries = summarize_conditions(case_rows)
    family_summaries = summarize_families(case_rows)
    curve_summaries = summarize_curves(case_rows, curve_rows)
    paired = paired_differences(case_rows)
    paired_stats = paired_statistics(
        paired, config.get("statistical_analysis", {})
    )
    write_csv(output_dir / "case_metrics.csv", case_rows, case_columns)
    write_csv(output_dir / "curve_metrics.csv", curve_rows, curve_columns)
    write_csv(
        output_dir / "condition_summary.csv",
        summaries,
        [
            "condition",
            "cases",
            "valid_axis_fit_cases",
            "curve_count_correct_cases",
            "geometry_complete_pass_cases",
            "complete_pass_cases",
            "median_case_scaled_distance",
            "mean_case_scaled_distance",
            "median_elapsed_seconds",
            "total_model_calls",
        ],
    )
    write_csv(
        output_dir / "family_summary.csv",
        family_summaries,
        [
            "condition",
            "family",
            "cases",
            "geometry_complete_pass_cases",
            "complete_pass_cases",
            "curve_count_correct_cases",
            "median_case_scaled_distance",
        ],
    )
    write_csv(
        output_dir / "curve_summary.csv",
        curve_summaries,
        [
            "condition",
            "truth_curves",
            "predicted_curves",
            "matched_curves",
            "geometry_pass_curves",
            "identity_exact_curves",
            "median_curve_scaled_distance",
        ],
    )
    write_csv(
        output_dir / "paired_case_differences.csv",
        paired,
        [
            "case_id",
            "family",
            "monolithic_case_median_scaled_distance",
            "staged_case_median_scaled_distance",
            "staged_minus_monolithic",
            "staged_better",
            "monolithic_complete_pass",
            "staged_complete_pass",
        ],
    )
    write_json(output_dir / "paired_statistics.json", paired_stats)
    write_json(output_dir / "evaluation_errors.json", errors)
    (output_dir / "summary.md").write_text(
        evaluation_markdown(
            summaries,
            family_summaries,
            curve_summaries,
            paired,
            paired_stats,
            errors,
        ),
        encoding="utf-8",
    )
    print(f"Evaluation written to {output_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a leakage-safe monolithic-versus-staged curve benchmark."
    )
    parser.add_argument(
        "action",
        choices=("prepare", "run-monolithic", "run-staged", "evaluate"),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--case-source", type=Path, default=DEFAULT_CASE_SOURCE)
    parser.add_argument("--truth-source", type=Path, default=DEFAULT_TRUTH_SOURCE)
    parser.add_argument("--code-archive", type=Path, default=DEFAULT_CODE_ARCHIVE)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument(
        "--condition",
        action="append",
        choices=("monolithic", "staged"),
        default=[],
        help="Limit evaluation to one or more completed benchmark conditions.",
    )
    parser.add_argument("--replicate", type=int, default=1)
    parser.add_argument("--model", default="")
    parser.add_argument("--reasoning-effort", default="")
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--codex-cmd", default="")
    parser.add_argument(
        "--codex-bypass-sandbox",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Use the same unrestricted local Python/file access for both conditions. "
            "The default is read from benchmark_config.json."
        ),
    )
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument(
        "--force-prepare",
        action="store_true",
        help="Reset existing prepared condition directories under --run-root.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config.resolve())
    if args.action == "prepare":
        prepare(args, config)
    elif args.action == "run-monolithic":
        run_monolithic(args, config)
    elif args.action == "run-staged":
        run_staged(args, config)
    elif args.action == "evaluate":
        evaluate(args, config)
    else:
        parser.error(f"Unsupported action: {args.action}")


if __name__ == "__main__":
    main()
