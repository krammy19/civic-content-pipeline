"""Tests for the `civic` console command's dispatch and argument
parsing. This is a thin wrapper - no business logic lives in cli.py -
so these tests mock the real function each subcommand delegates to
and assert the delegation happened with the right arguments, rather
than re-testing the underlying modules (already covered by their own
test suites). No live API calls anywhere in this file."""

import json
from unittest.mock import patch

from civic_scraper import cli


class TestMainDispatch:
    def test_no_args_prints_usage_and_exits_zero(self, capsys):
        assert cli.main([]) == 0
        assert "usage: civic" in capsys.readouterr().out

    def test_help_flag_prints_usage(self, capsys):
        assert cli.main(["--help"]) == 0
        assert "commands:" in capsys.readouterr().out

    def test_unknown_command_exits_nonzero(self, capsys):
        result = cli.main(["not-a-real-command"])
        assert result == 1
        assert "Unknown command" in capsys.readouterr().out

    def test_dispatches_to_the_right_handler(self):
        # _COMMANDS holds direct function references, so the patch target
        # is the dict entry itself, not a same-named module attribute.
        received = []
        with patch.dict(cli._COMMANDS, {"metrics": received.append}):
            result = cli.main(["metrics", "--city", "San Jose"])
        assert received == [["--city", "San Jose"]]
        assert result is None  # list.append's return value, passed straight through


class TestCmdIngest:
    def test_delegates_to_run_all_main_with_remaining_argv(self):
        with patch("civic_scraper.run_all.main", return_value=0) as run_all_main:
            cli.main(["ingest", "--city", "Oakland"])
        run_all_main.assert_called_once_with(["--city", "Oakland"])


class TestCmdReview:
    def test_delegates_to_review_cli_main(self):
        with patch("civic_scraper.review.cli.main", return_value=0) as review_main:
            result = cli.main(["review"])
        review_main.assert_called_once_with()
        assert result == 0


class TestCmdExtract:
    def test_reads_item_file_and_calls_extract_agenda_item(self, tmp_path, capsys):
        item_file = tmp_path / "item.json"
        item_file.write_text(
            json.dumps(
                {
                    "item_title": "Test item",
                    "item_number": "2.8",
                    "source_document": "doc",
                    "document_text": "The Council approved it.",
                }
            ),
            encoding="utf-8",
        )

        fake_result = type("FakeItem", (), {"model_dump_json": lambda self, indent=2: "{}"})()

        with patch(
            "civic_scraper.extraction.agenda_item.extract_agenda_item",
            return_value=fake_result,
        ) as extract:
            result = cli.main(["extract", str(item_file)])

        assert result == 0
        extract.assert_called_once_with(
            item_title="Test item",
            item_number="2.8",
            source_document="doc",
            document_text="The Council approved it.",
            model="claude-sonnet-5",
        )
        assert capsys.readouterr().out.strip() == "{}"


class TestCmdDigest:
    def test_reads_meeting_file_and_calls_generate_digest(self, tmp_path, capsys):
        meeting_file = tmp_path / "meeting.json"
        meeting_file.write_text(
            json.dumps(
                {
                    "source": "legistar",
                    "jurisdiction": "San Jose",
                    "body": "City Council",
                    "date": "2026-06-09",
                }
            ),
            encoding="utf-8",
        )

        with patch(
            "civic_scraper.digest.generate_digest.generate_digest", return_value="# Digest"
        ) as generate:
            result = cli.main(["digest", str(meeting_file)])

        assert result == 0
        assert generate.call_count == 1
        assert capsys.readouterr().out.strip() == "# Digest"


class TestCmdCheck:
    def test_no_high_severity_findings_exits_zero(self, tmp_path):
        digest_file = tmp_path / "digest.md"
        digest_file.write_text("# Title\n\n## Overview\n\nx\n", encoding="utf-8")

        with (
            patch("checks.style_check.check_deterministic", return_value=[]),
            patch("checks.style_check.judge_style", return_value=[]),
        ):
            result = cli.main(["check", str(digest_file)])

        assert result == 0

    def test_high_severity_finding_exits_nonzero(self, tmp_path):
        from checks.style_check import Finding

        digest_file = tmp_path / "digest.md"
        digest_file.write_text("bad digest", encoding="utf-8")

        with (
            patch(
                "checks.style_check.check_deterministic",
                return_value=[Finding("missing_header", "high", "no header")],
            ),
            patch("checks.style_check.judge_style", return_value=[]),
        ):
            result = cli.main(["check", str(digest_file)])

        assert result == 1


class TestCmdEval:
    def test_delegates_to_run_eval_main(self):
        with patch("evals.run_eval.main", return_value=0) as run_eval_main:
            result = cli.main(["eval", "--update-baseline"])
        run_eval_main.assert_called_once_with(["--update-baseline"])
        assert result == 0


class TestCmdMetrics:
    def test_no_history_says_so(self, capsys):
        with patch("civic_scraper.metrics.store.load_run_history", return_value=[]):
            result = cli.main(["metrics", "--city", "Nowhere"])
        assert result == 0
        assert "No recorded runs" in capsys.readouterr().out

    def test_requires_city_argument(self):
        try:
            cli.main(["metrics"])
        except SystemExit as exc:
            assert exc.code != 0
        else:
            raise AssertionError("expected argparse to exit on a missing required argument")
