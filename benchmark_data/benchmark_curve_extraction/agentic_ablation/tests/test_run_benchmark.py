from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "run_benchmark.py"
SPEC = importlib.util.spec_from_file_location("run_benchmark", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
benchmark = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = benchmark
SPEC.loader.exec_module(benchmark)


class AxisFitTests(unittest.TestCase):
    def test_linear_axis_fit(self) -> None:
        anchors = [
            {
                "tick_value": "0",
                "pixel_x": 10,
                "pixel_y": 0,
                "coordinate_system": "cropped_panel",
            },
            {
                "tick_value": "5",
                "pixel_x": 60,
                "pixel_y": 0,
                "coordinate_system": "cropped_panel",
            },
            {
                "tick_value": "10",
                "pixel_x": 110,
                "pixel_y": 0,
                "coordinate_system": "cropped_panel",
            },
        ]
        fit = benchmark.fit_axis(anchors, "x", "linear", [20, 30, 0, 0])
        self.assertEqual(fit.anchor_count, 3)
        self.assertAlmostEqual(fit.value(80), 5.0)
        self.assertAlmostEqual(fit.rmse, 0.0)

    def test_log_axis_fit(self) -> None:
        anchors = [
            {
                "tick_value": "1",
                "pixel_x": 0,
                "pixel_y": 10,
                "coordinate_system": "original_figure",
            },
            {
                "tick_value": "10",
                "pixel_x": 0,
                "pixel_y": 60,
                "coordinate_system": "original_figure",
            },
            {
                "tick_value": "100",
                "pixel_x": 0,
                "pixel_y": 110,
                "coordinate_system": "original_figure",
            },
        ]
        fit = benchmark.fit_axis(anchors, "y", "log10", [0, 0, 0, 0])
        self.assertEqual(fit.model, "log10")
        self.assertAlmostEqual(fit.value(85), math.sqrt(1000), places=9)

    def test_unicode_minus_tick(self) -> None:
        self.assertEqual(benchmark.parse_number("−0.25"), -0.25)

    def test_power_of_ten_tick(self) -> None:
        self.assertEqual(benchmark.parse_number("10^-1"), 0.1)
        self.assertEqual(benchmark.parse_number("10^{2}"), 100.0)

    def test_truth_display_axis_override(self) -> None:
        config = {
            "default": {"x": "linear", "y": "linear"},
            "overrides": {"a_lsv_08": {"y": "log10"}},
        }
        self.assertEqual(
            benchmark.truth_display_models(config, "a_lsv_08"),
            ("linear", "log10"),
        )
        self.assertEqual(
            benchmark.truth_display_models(config, "a_lsv_01"),
            ("linear", "linear"),
        )


class CurveMetricTests(unittest.TestCase):
    def test_identical_curves_have_zero_distance(self) -> None:
        curve = {"points": [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]}
        metrics = benchmark.pair_metrics(curve, curve, (0.0, 1.0, 0.0, 1.0))
        self.assertAlmostEqual(metrics["median_scaled_distance"], 0.0)
        self.assertAlmostEqual(metrics["p95_scaled_distance"], 0.0)
        self.assertAlmostEqual(metrics["x_coverage"], 1.0)

    def test_shifted_curve_has_positive_distance(self) -> None:
        predicted = {"points": [(0.0, 0.1), (0.5, 0.6), (1.0, 1.1)]}
        truth = {"points": [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]}
        metrics = benchmark.pair_metrics(predicted, truth, (0.0, 1.0, 0.0, 1.0))
        self.assertGreater(metrics["median_scaled_distance"], 0.05)

    def test_assignment_finds_crossed_minimum(self) -> None:
        assignment = benchmark.best_assignment([[9.0, 1.0], [1.0, 9.0]])
        self.assertEqual(sorted(assignment), [(0, 1), (1, 0)])

    def test_label_normalization_handles_latex(self) -> None:
        self.assertEqual(
            benchmark.normalize_label("IrO$_2$"),
            benchmark.normalize_label("IrO2"),
        )

    def test_exact_sign_test(self) -> None:
        negatives, positives, ties, probability = benchmark.exact_sign_test(
            [-1.0, -0.5, -0.1, 0.2, 0.0]
        )
        self.assertEqual((negatives, positives, ties), (3, 1, 1))
        self.assertAlmostEqual(probability, 0.625)

    def test_bootstrap_interval_is_deterministic(self) -> None:
        first = benchmark.bootstrap_median_interval(
            [-0.2, -0.1, 0.0, 0.1], 1000, 0.95, 42
        )
        second = benchmark.bootstrap_median_interval(
            [-0.2, -0.1, 0.0, 0.1], 1000, 0.95, 42
        )
        self.assertEqual(first, second)

    def test_codex_text_token_summary_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "stderr.log"
            log.write_text("progress\ntokens used\n88,285\n", encoding="utf-8")
            self.assertEqual(benchmark.parse_codex_reported_tokens(log), 88285)

    def test_json_usage_derives_total_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            events = Path(directory) / "events.jsonl"
            events.write_text(
                json.dumps({"usage": {"input_tokens": 100, "output_tokens": 20}}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(benchmark.parse_usage(events)["total_tokens"], 120)


class IsolationTests(unittest.TestCase):
    def test_sanitized_task_replaces_source_path(self) -> None:
        task = {
            "case_id": "a_lsv_01",
            "paper_id": "paper",
            "figure_id": "figure",
            "panel_id": "panel",
            "image_path": r"C:\private\source.png",
            "special_notes": "Inspect the image.",
        }
        clean = benchmark.sanitize_task(task, Path("worker") / "panel.png")
        self.assertNotIn("private", clean["image_path"].lower())
        self.assertIn("do not inspect other cases", clean["special_notes"].lower())

    def test_worker_tree_audit_rejects_answer_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "case").mkdir()
            (root / "case" / "panel.png").write_bytes(b"png")
            self.assertEqual(benchmark.audit_worker_tree(root), [])
            (root / "case" / "ground_truth.csv").write_text(
                "x,y\n0,0\n", encoding="utf-8"
            )
            self.assertTrue(benchmark.audit_worker_tree(root))

    def test_monolithic_prompt_has_no_unresolved_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case_dir = Path(directory)
            (case_dir / "tools").mkdir()
            image = case_dir / "panel.png"
            image.write_bytes(b"png")
            task = {
                "paper_id": "paper",
                "figure_id": "figure",
                "panel_id": "panel",
                "panel_label": "a",
                "image_path": str(image),
                "figure_caption": "Caption",
                "caption_snippet": "Caption",
                "candidate_catalysts": [],
                "special_notes": "",
            }
            prompt, _ = benchmark.prompt_for_case(case_dir, task)
            self.assertNotRegex(prompt, r"\[[A-Z][A-Z0-9_]+\]")

    def test_config_and_schema_are_valid_json(self) -> None:
        base = Path(__file__).resolve().parents[1]
        config = json.loads((base / "benchmark_config.json").read_text(encoding="utf-8"))
        schema = json.loads(
            (base / "schemas" / "monolithic_anchor_extract.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(config["benchmark_case_set"], benchmark.DEFAULT_CASE_SET)
        self.assertEqual(config["model"], "gpt-5.4")
        self.assertEqual(config["reasoning_effort"], "xhigh")
        self.assertEqual(config["max_workers"], 60)
        self.assertEqual(config["provider"]["env_key"], "BLACKAI_API_KEY")
        self.assertEqual(config["provider"]["base_url"], "https://blackaicoding.com/v1")
        self.assertNotIn("api_key", config["provider"])
        self.assertEqual(schema["type"], "object")

    def test_provider_environment_isolated_from_local_openai_credentials(self) -> None:
        config = {
            "provider": {
                "id": "test_provider",
                "name": "Test Provider",
                "base_url": "https://example.invalid/",
                "env_key": "TEST_PROVIDER_KEY",
                "wire_api": "responses",
                "requires_openai_auth": False,
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            environment, audit = benchmark.build_provider_environment(
                config,
                Path(directory),
                base_environment={
                    "PATH": os.environ.get("PATH", ""),
                    "TEST_PROVIDER_KEY": "test-secret-not-for-network-use",
                    "OPENAI_API_KEY": "must-be-removed",
                    "OPENAI_BASE_URL": "https://must-be-removed.invalid/",
                },
            )
            self.assertEqual(environment["TEST_PROVIDER_KEY"], "test-secret-not-for-network-use")
            self.assertNotIn("OPENAI_API_KEY", environment)
            self.assertNotIn("OPENAI_BASE_URL", environment)
            self.assertFalse(audit["local_openai_credentials_inherited"])
            config_text = Path(audit["config_path"]).read_text(encoding="utf-8")
            self.assertIn('model_provider = "test_provider"', config_text)
            self.assertIn('env_key = "TEST_PROVIDER_KEY"', config_text)
            self.assertNotIn("test-secret-not-for-network-use", config_text)

    def test_provider_environment_requires_dedicated_key(self) -> None:
        config = {
            "provider": {
                "id": "test_provider",
                "name": "Test Provider",
                "base_url": "https://example.invalid/",
                "env_key": "TEST_PROVIDER_KEY",
                "wire_api": "responses",
                "requires_openai_auth": False,
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "TEST_PROVIDER_KEY"):
                benchmark.build_provider_environment(
                    config,
                    Path(directory),
                    base_environment={"OPENAI_API_KEY": "must-not-be-used"},
                )

    def test_each_worker_gets_an_independent_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_home = root / "provider"
            base_home.mkdir()
            (base_home / "config.toml").write_text(
                'model_provider = "test_provider"\n', encoding="utf-8"
            )
            environment = {
                "CODEX_HOME": str(base_home),
                "TEST_PROVIDER_KEY": "test-secret-not-for-network-use",
            }
            first = benchmark.isolate_worker_provider_environment(
                environment, root / "case_01"
            )
            second = benchmark.isolate_worker_provider_environment(
                environment, root / "case_02"
            )
            self.assertNotEqual(first["CODEX_HOME"], second["CODEX_HOME"])
            self.assertEqual(
                Path(first["CODEX_HOME"], "config.toml").read_text(encoding="utf-8"),
                'model_provider = "test_provider"\n',
            )
            self.assertEqual(
                first["TEST_PROVIDER_KEY"], "test-secret-not-for-network-use"
            )

    def test_monolithic_command_attaches_image_and_locks_effort(self) -> None:
        command = benchmark.build_monolithic_command(
            codex_cmd="codex.cmd",
            case_dir=Path("case"),
            response_path=Path("response.json"),
            image_path=Path("panel.png"),
            model="gpt-5.4",
            reasoning_effort="xhigh",
            codex_bypass_sandbox=True,
            attach_input_image=True,
        )
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertEqual(command[command.index("-m") + 1], "gpt-5.4")
        self.assertIn('model_reasoning_effort="xhigh"', command)
        self.assertEqual(command[command.index("-i") + 1], "panel.png")

    def test_provider_preflight_requires_requested_model(self) -> None:
        config = {
            "provider": {
                "id": "test_provider",
                "name": "Test Provider",
                "base_url": "https://example.invalid/v1",
                "env_key": "TEST_PROVIDER_KEY",
                "wire_api": "responses",
                "requires_openai_auth": False,
            }
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps({"data": [{"id": "gpt-5.4"}]}).encode("utf-8")

        def fake_opener(_request, **_kwargs):
            return FakeResponse()

        audit = benchmark.provider_model_preflight(
            config,
            {"TEST_PROVIDER_KEY": "test-only"},
            "gpt-5.4",
            opener=fake_opener,
        )
        self.assertTrue(audit["requested_model_available"])
        self.assertEqual(audit["model_count"], 1)


class EndToEndEvaluatorTests(unittest.TestCase):
    def test_exact_monolithic_fixture_scores_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth_root = root / "truth"
            truth_root.mkdir()
            (truth_root / "case_truth_index.csv").write_text(
                "case_id,curve_family,raw_data_file,metadata_file\n"
                "case_01,LSV,case_raw.csv,case_metadata.json\n",
                encoding="utf-8",
            )
            (truth_root / "case_metadata.json").write_text(
                json.dumps(
                    {
                        "curve_family": "LSV",
                        "x_column": "x",
                        "y_column": "y",
                        "series_column": "series",
                    }
                ),
                encoding="utf-8",
            )
            (truth_root / "case_raw.csv").write_text(
                "series,x,y\nCatalyst A,0,0\nCatalyst A,0.5,0.5\nCatalyst A,1,1\n",
                encoding="utf-8",
            )
            case_dir = root / "case_01"
            response_dir = case_dir / "monolithic_anchor_extract"
            response_dir.mkdir(parents=True)
            response = {
                "paper_id": "paper",
                "figure_id": "figure",
                "panel_id": "panel",
                "panel_label": "panel",
                "saved_panel_image_path": "",
                "saved_curve_overlay_path": "",
                "crop_box_original": [0, 0, 100, 100],
                "plot_area_box_cropped": [0, 0, 100, 100],
                "panel_type": "line_plot",
                "x_axis": {
                    "label": "x",
                    "units": "",
                    "tick_labels": ["0", "1"],
                    "chosen_model": "linear",
                    "usable_for_downstream": "yes",
                    "anchors": [
                        {
                            "tick_value": "0",
                            "pixel_x": 0,
                            "pixel_y": 100,
                            "coordinate_system": "cropped_panel",
                            "confidence": 1,
                            "note": "",
                        },
                        {
                            "tick_value": "1",
                            "pixel_x": 100,
                            "pixel_y": 100,
                            "coordinate_system": "cropped_panel",
                            "confidence": 1,
                            "note": "",
                        },
                    ],
                    "fit_notes": "",
                },
                "y_axis": {
                    "label": "y",
                    "units": "",
                    "tick_labels": ["0", "1"],
                    "chosen_model": "linear",
                    "usable_for_downstream": "yes",
                    "anchors": [
                        {
                            "tick_value": "0",
                            "pixel_x": 0,
                            "pixel_y": 100,
                            "coordinate_system": "cropped_panel",
                            "confidence": 1,
                            "note": "",
                        },
                        {
                            "tick_value": "1",
                            "pixel_x": 0,
                            "pixel_y": 0,
                            "coordinate_system": "cropped_panel",
                            "confidence": 1,
                            "note": "",
                        },
                    ],
                    "fit_notes": "",
                },
                "legend_entries": ["Catalyst A"],
                "curves": [
                    {
                        "curve_id": "curve_1",
                        "curve_label": "Catalyst A",
                        "condition_label": "",
                        "catalyst_context": "",
                        "stroke_color": "blue",
                        "line_style": "solid",
                        "marker_style": "none",
                        "point_coordinate_system": "cropped_panel",
                        "sampled_points": [
                            {"pixel_x": 0, "pixel_y": 100, "confidence": 1},
                            {"pixel_x": 50, "pixel_y": 50, "confidence": 1},
                            {"pixel_x": 100, "pixel_y": 0, "confidence": 1},
                        ],
                        "visible_segment_status": "complete",
                        "overlap_notes": "",
                        "usable_for_normalization": "yes",
                        "confidence": 1,
                    }
                ],
                "interpretation_notes": "",
                "qc": {
                    "axis_fit_script_used": True,
                    "overlap_qa_used": True,
                    "curve_count_estimated_correctly": True,
                    "legend_curve_mapping_complete": "yes",
                    "points_cover_visible_extent": "yes",
                    "manual_review_required": False,
                },
                "unresolved_ambiguities": [],
            }
            (response_dir / "response.json").write_text(
                json.dumps(response), encoding="utf-8"
            )
            index = benchmark.truth_index_by_case(truth_root)
            case_row, curve_rows = benchmark.evaluate_case(
                "monolithic",
                "case_01",
                case_dir,
                truth_root,
                index,
                {
                    "curve_median_scaled_distance_max": 0.02,
                    "curve_p95_scaled_distance_max": 0.05,
                    "x_coverage_min": 0.8,
                },
            )
            self.assertAlmostEqual(
                case_row["case_median_symmetric_scaled_distance"], 0.0
            )
            self.assertTrue(case_row["case_complete_pass"])
            self.assertTrue(curve_rows[0]["identity_exact"])


if __name__ == "__main__":
    unittest.main()
