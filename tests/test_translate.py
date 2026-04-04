"""Tests for the business-language translation engine."""

from __future__ import annotations

import pytest

from visualpy.models import Service, Step, Trigger
from visualpy.translate import (
    BUSINESS_LABELS,
    PHASE_LABELS,
    PHASE_ORDER,
    TECHNICAL_LABELS,
    TECHNICAL_LABELS_SHORT,
    deduplicate_steps,
    group_steps_by_phase,
    infer_phase,
    translate_connection,
    translate_secret,
    translate_step,
    translate_trigger,
)


def _step(step_type: str, description: str, service: Service | None = None) -> Step:
    """Shorthand to build a Step for testing."""
    return Step(line_number=1, type=step_type, description=description, service=service)


# --- translate_step: api_call ------------------------------------------------


class TestTranslateStepApiCall:
    def test_with_service_get(self):
        svc = Service(name="Google Sheets", library="gspread")
        result = translate_step(_step("api_call", "gspread.authorize()", svc))
        assert result == "Authenticates with Google Sheets"

    def test_with_service_post(self):
        svc = Service(name="HTTP Client", library="requests")
        result = translate_step(_step("api_call", "requests.post()", svc))
        assert result == "Sends data to HTTP Client"

    def test_with_service_default_verb(self):
        svc = Service(name="Apify", library="apify_client")
        result = translate_step(_step("api_call", "client.get()", svc))
        assert result == "Fetches data from Apify"

    def test_without_service(self):
        result = translate_step(_step("api_call", "client.get()"))
        assert result == "Fetches data from external service"

    def test_delete_verb(self):
        svc = Service(name="HTTP Client", library="requests")
        result = translate_step(_step("api_call", "requests.delete()", svc))
        assert result == "Removes data from HTTP Client"


# --- translate_step: file_io -------------------------------------------------


class TestTranslateStepFileIo:
    def test_read_json_load(self):
        result = translate_step(_step("file_io", "json.load()"))
        assert result == "Reads data from file"

    def test_write_json_dump(self):
        result = translate_step(_step("file_io", "json.dump()"))
        assert result == "Saves data to file"

    def test_open_plain(self):
        result = translate_step(_step("file_io", "open()"))
        assert result == "Opens file"

    def test_read_text(self):
        result = translate_step(_step("file_io", ".read_text()"))
        assert result == "Reads data from file"

    def test_write_to_csv(self):
        result = translate_step(_step("file_io", ".to_csv()"))
        assert result == "Saves data to file"


# --- translate_step: db_op ---------------------------------------------------


class TestTranslateStepDbOp:
    def test_query(self):
        result = translate_step(_step("db_op", "cursor.execute()"))
        assert result == "Queries database"

    def test_insert(self):
        result = translate_step(_step("db_op", ".insert()"))
        assert result == "Saves to database"

    def test_commit(self):
        result = translate_step(_step("db_op", ".commit()"))
        assert result == "Saves to database"


# --- translate_step: decision ------------------------------------------------


class TestTranslateStepDecision:
    def test_try_except(self):
        result = translate_step(_step("decision", "try/except block"))
        assert result == "Handles potential errors"

    def test_for_loop(self):
        result = translate_step(_step("decision", "for item in items"))
        assert result == "Processes each item"

    def test_for_loop_complex(self):
        result = translate_step(_step("decision", "for (k, v) in data.items()"))
        assert result == "Processes each k"

    def test_while_loop(self):
        result = translate_step(_step("decision", "while time.time() - start < max"))
        assert result == "Repeats while condition is met"

    def test_if_not(self):
        result = translate_step(_step("decision", "if not self.project_title"))
        assert "is missing" in result
        assert "project_title" in result

    def test_if_is_none(self):
        result = translate_step(_step("decision", "if value is None"))
        assert "is empty" in result

    def test_if_generic(self):
        result = translate_step(_step("decision", "if len(sys.argv) > 1"))
        assert result.startswith("Checks:")

    def test_if_path_exists(self):
        result = translate_step(_step("decision", "if not os.path.exists('token.json')"))
        assert "file doesn't exist" in result


# --- translate_step: output --------------------------------------------------


class TestTranslateStepOutput:
    def test_print(self):
        result = translate_step(_step("output", "print()"))
        assert result == "Displays message"

    def test_logger_info(self):
        result = translate_step(_step("output", "logger.info()"))
        assert result == "Records activity"

    def test_logger_error(self):
        result = translate_step(_step("output", "logger.error()"))
        assert result == "Records an error"

    def test_logger_warning(self):
        result = translate_step(_step("output", "logger.warning()"))
        assert result == "Records a warning"


# --- translate_step: transform -----------------------------------------------


class TestTranslateStepTransform:
    def test_list_comprehension(self):
        result = translate_step(_step("transform", "list comprehension: [x for ...]"))
        assert result == "Builds a collection of items"

    def test_split(self):
        result = translate_step(_step("transform", ".split()"))
        assert result == "Splits text into parts"

    def test_join(self):
        result = translate_step(_step("transform", ".join()"))
        assert result == "Joins text together"

    def test_sorted(self):
        result = translate_step(_step("transform", "sorted()"))
        assert result == "Sorts data"

    def test_int_conversion(self):
        result = translate_step(_step("transform", "int()"))
        assert result == "Converts data type"

    def test_str_conversion(self):
        result = translate_step(_step("transform", "str()"))
        assert result == "Converts data type"

    def test_encode(self):
        result = translate_step(_step("transform", ".encode()"))
        assert result == "Converts text encoding"

    def test_json_loads(self):
        result = translate_step(_step("transform", ".loads()"))
        assert result == "Converts data format"

    def test_strip(self):
        result = translate_step(_step("transform", ".strip()"))
        assert result == "Cleans up text"

    def test_len(self):
        result = translate_step(_step("transform", "len()"))
        assert result == "Counts items"

    def test_fallback(self):
        result = translate_step(_step("transform", "some_unknown_op()"))
        assert result == "Processes data"


# --- translate_trigger -------------------------------------------------------


class TestTranslateTrigger:
    def test_cron_daily(self):
        result = translate_trigger(Trigger(type="cron", detail="0 0 * * *"))
        assert result == "Runs daily at midnight"

    def test_cron_every_5_min(self):
        result = translate_trigger(Trigger(type="cron", detail="*/5 * * * *"))
        assert result == "Runs every 5 minutes"

    def test_cron_hourly(self):
        result = translate_trigger(Trigger(type="cron", detail="0 * * * *"))
        assert result == "Runs every hour"

    def test_cron_weekly(self):
        result = translate_trigger(Trigger(type="cron", detail="0 0 * * 0"))
        assert result == "Runs weekly on Sunday"

    def test_cron_fallback(self):
        result = translate_trigger(Trigger(type="cron", detail="15 3 * * 2,4"))
        assert result == "Runs on a schedule"

    def test_cli_main_guard(self):
        result = translate_trigger(Trigger(type="cli", detail="__main__ guard"))
        assert result == "Can be run directly"

    def test_cli_argparse(self):
        result = translate_trigger(Trigger(type="cli", detail="argparse"))
        assert result == "Accepts command-line options"

    def test_cli_click(self):
        result = translate_trigger(Trigger(type="cli", detail="click: my_cmd"))
        assert result == "Command: my_cmd"

    def test_webhook_post(self):
        result = translate_trigger(Trigger(type="webhook", detail="POST /hook/intake"))
        assert result == "Triggered by web request to /hook/intake"

    def test_webhook_modal(self):
        result = translate_trigger(Trigger(type="webhook", detail="modal endpoint: predict"))
        assert result == "Cloud function: predict"

    def test_import(self):
        result = translate_trigger(Trigger(type="import", detail="imported by main.py"))
        assert result == "Used by other scripts"

    def test_manual(self):
        result = translate_trigger(Trigger(type="manual", detail=""))
        assert result == "Run manually"

    def test_unknown_type(self):
        result = translate_trigger(Trigger(type="custom", detail="something"))
        assert result == "Custom"


# --- translate_secret --------------------------------------------------------


class TestTranslateSecret:
    def test_aws(self):
        assert translate_secret("AWS_SECRET_ACCESS_KEY") == "AWS credentials"

    def test_google(self):
        assert translate_secret("GOOGLE_APPLICATION_CREDENTIALS") == "Google credentials"

    def test_openai(self):
        assert translate_secret("OPENAI_API_KEY") == "OpenAI credentials"

    def test_anthropic(self):
        assert translate_secret("ANTHROPIC_API_KEY") == "Anthropic credentials"

    def test_apify(self):
        assert translate_secret("APIFY_API_TOKEN") == "Apify credentials"

    def test_pandadoc(self):
        assert translate_secret("PANDADOC_API_KEY") == "PandaDoc credentials"

    def test_generic_api_key(self):
        result = translate_secret("CUSTOM_SERVICE_API_KEY")
        assert "credentials" in result
        assert "Custom Service" in result

    def test_generic_token(self):
        result = translate_secret("MY_SERVICE_TOKEN")
        assert "credentials" in result

    def test_unknown_fallback(self):
        result = translate_secret("DEBUG")
        assert result == "Configuration: DEBUG"

    def test_slack(self):
        assert translate_secret("SLACK_WEBHOOK_URL") == "Slack credentials"


# --- translate_connection ----------------------------------------------------


class TestTranslateConnection:
    def test_import(self):
        assert translate_connection("import") == "uses"

    def test_file_io(self):
        assert translate_connection("file_io") == "shares data with"

    def test_subprocess(self):
        assert translate_connection("subprocess") == "launches"

    def test_trigger(self):
        assert translate_connection("trigger") == "triggers"

    def test_unknown(self):
        assert translate_connection("custom") == "custom"


# --- Label completeness ------------------------------------------------------


class TestLabelCompleteness:
    ALL_STEP_TYPES = {"api_call", "file_io", "db_op", "decision", "output", "transform"}

    def test_business_labels_cover_all_types(self):
        assert set(BUSINESS_LABELS.keys()) == self.ALL_STEP_TYPES

    def test_technical_labels_cover_all_types(self):
        assert set(TECHNICAL_LABELS.keys()) == self.ALL_STEP_TYPES

    def test_short_labels_cover_all_types(self):
        assert set(TECHNICAL_LABELS_SHORT.keys()) == self.ALL_STEP_TYPES

    def test_business_labels_are_nonempty(self):
        for key, val in BUSINESS_LABELS.items():
            assert val, f"Empty business label for {key}"

    def test_technical_labels_are_nonempty(self):
        for key, val in TECHNICAL_LABELS.items():
            assert val, f"Empty technical label for {key}"

    def test_short_labels_are_nonempty(self):
        for key, val in TECHNICAL_LABELS_SHORT.items():
            assert val, f"Empty short label for {key}"


# --- Edge cases --------------------------------------------------------------


class TestEdgeCases:
    def test_empty_description(self):
        result = translate_step(_step("api_call", ""))
        assert result  # should not crash or return empty

    def test_unknown_step_type(self):
        result = translate_step(_step("custom_type", "whatever"))
        assert result == "Custom type"

    def test_secret_empty_string(self):
        result = translate_secret("")
        assert "Configuration" in result

    def test_secret_only_suffix(self):
        result = translate_secret("_API_KEY")
        assert result == "API credentials"

    def test_cron_empty_detail(self):
        result = translate_trigger(Trigger(type="cron", detail=""))
        assert result == "Runs on a schedule"

    def test_empty_trigger_detail(self):
        result = translate_trigger(Trigger(type="cli", detail=""))
        assert result == "Run from command line"

    def test_file_io_with_quoted_path(self):
        result = translate_step(_step("file_io", "open('config.json')"))
        assert result == "Opens file"


# --- infer_phase -------------------------------------------------------------


class TestInferPhase:
    def test_try_except_is_error_handling(self):
        assert infer_phase(_step("decision", "try/except block")) == "error_handling"

    def test_for_loop_is_processing(self):
        assert infer_phase(_step("decision", "for item in items")) == "processing"

    def test_while_loop_is_processing(self):
        assert infer_phase(_step("decision", "while time.time() < max")) == "processing"

    def test_print_is_reporting(self):
        assert infer_phase(_step("output", "print()")) == "reporting"

    def test_logger_is_reporting(self):
        assert infer_phase(_step("output", "logger.info()")) == "reporting"

    def test_transform_is_processing(self):
        assert infer_phase(_step("transform", ".split()")) == "processing"

    def test_api_get_is_setup(self):
        assert infer_phase(_step("api_call", "requests.get()")) == "setup"

    def test_api_post_is_storage(self):
        assert infer_phase(_step("api_call", "requests.post()")) == "storage"

    def test_api_authorize_is_setup(self):
        assert infer_phase(_step("api_call", "gspread.authorize()")) == "setup"

    def test_file_read_is_setup(self):
        assert infer_phase(_step("file_io", "json.load()")) == "setup"

    def test_file_write_is_storage(self):
        assert infer_phase(_step("file_io", "json.dump()")) == "storage"

    def test_file_to_csv_is_storage(self):
        assert infer_phase(_step("file_io", ".to_csv()")) == "storage"

    def test_file_open_is_setup(self):
        assert infer_phase(_step("file_io", "open()")) == "setup"

    def test_db_query_is_setup(self):
        assert infer_phase(_step("db_op", "cursor.execute()")) == "setup"

    def test_db_insert_is_storage(self):
        assert infer_phase(_step("db_op", ".insert()")) == "storage"

    def test_db_commit_is_storage(self):
        assert infer_phase(_step("db_op", ".commit()")) == "storage"

    def test_if_condition_is_processing(self):
        assert infer_phase(_step("decision", "if value is None")) == "processing"

    def test_unknown_type_is_processing(self):
        assert infer_phase(_step("custom_type", "whatever")) == "processing"

    def test_empty_description_no_crash(self):
        result = infer_phase(_step("api_call", ""))
        assert result in PHASE_ORDER

    def test_api_delete_is_storage(self):
        assert infer_phase(_step("api_call", "requests.delete()")) == "storage"

    def test_list_comprehension_is_processing(self):
        assert infer_phase(_step("transform", "list comprehension: [x for ...]")) == "processing"

    def test_send_is_storage(self):
        assert infer_phase(_step("api_call", "slack.send(msg)")) == "storage"


# --- group_steps_by_phase ---------------------------------------------------


class TestGroupStepsByPhase:
    def test_groups_mixed_steps(self):
        steps = [
            _step("api_call", "requests.get()"),       # setup
            _step("transform", ".split()"),             # processing
            _step("file_io", "json.dump()"),            # storage
            _step("output", "print()"),                 # reporting
            _step("decision", "try/except block"),      # error_handling
        ]
        result = group_steps_by_phase(steps)
        phase_keys = [k for k, _, _ in result]
        assert phase_keys == ["setup", "processing", "storage", "error_handling", "reporting"]

    def test_empty_phases_omitted(self):
        steps = [
            _step("output", "print()"),
            _step("output", "logger.info()"),
        ]
        result = group_steps_by_phase(steps)
        assert len(result) == 1
        assert result[0][0] == "reporting"
        assert len(result[0][2]) == 2

    def test_empty_steps_returns_empty(self):
        assert group_steps_by_phase([]) == []

    def test_all_same_phase(self):
        steps = [_step("transform", f"op{i}") for i in range(5)]
        result = group_steps_by_phase(steps)
        assert len(result) == 1
        assert result[0][0] == "processing"
        assert len(result[0][2]) == 5

    def test_phase_labels_correct(self):
        steps = [_step("api_call", "requests.get()")]
        result = group_steps_by_phase(steps)
        assert result[0][1] == "Setup & Data Gathering"

    def test_phase_order_respected(self):
        """Steps added in reverse order should still group in PHASE_ORDER."""
        steps = [
            _step("output", "print()"),                 # reporting
            _step("decision", "try/except block"),      # error_handling
            _step("file_io", "json.dump()"),            # storage
            _step("transform", ".strip()"),             # processing
            _step("api_call", "requests.get()"),        # setup
        ]
        result = group_steps_by_phase(steps)
        phase_keys = [k for k, _, _ in result]
        assert phase_keys == ["setup", "processing", "storage", "error_handling", "reporting"]

    def test_phase_labels_completeness(self):
        """All PHASE_ORDER keys must exist in PHASE_LABELS."""
        for key in PHASE_ORDER:
            assert key in PHASE_LABELS, f"Missing label for phase {key}"


# --- deduplicate_steps (Sprint 7) -------------------------------------------


class TestDeduplicateSteps:
    def test_all_unique(self):
        steps = [
            _step("api_call", "requests.get()", Service(name="API", library="requests")),
            _step("file_io", "json.dump()"),
            _step("output", "print()"),
        ]
        result = deduplicate_steps(steps)
        assert len(result) == 3
        assert all(len(group) == 1 for _, group in result)

    def test_all_identical(self):
        steps = [
            Step(line_number=i, type="decision", description="try/except block")
            for i in range(1, 4)
        ]
        result = deduplicate_steps(steps)
        assert len(result) == 1
        assert result[0][0] == "Handles potential errors"
        assert len(result[0][1]) == 3

    def test_mixed(self):
        steps = [
            Step(line_number=1, type="decision", description="try/except block"),
            _step("output", "print()"),
            Step(line_number=3, type="decision", description="try/except block"),
        ]
        result = deduplicate_steps(steps)
        assert len(result) == 2
        assert result[0][0] == "Handles potential errors"
        assert len(result[0][1]) == 2
        assert result[1][0] == "Displays message"
        assert len(result[1][1]) == 1

    def test_empty_list(self):
        assert deduplicate_steps([]) == []

    def test_single_step(self):
        result = deduplicate_steps([_step("output", "print()")])
        assert len(result) == 1
        assert len(result[0][1]) == 1

    def test_preserves_first_occurrence_order(self):
        steps = [
            _step("output", "print()"),
            _step("api_call", "requests.get()"),
            Step(line_number=3, type="output", description="print()"),
        ]
        result = deduplicate_steps(steps)
        assert result[0][0] == "Displays message"
        assert result[1][0] == "Fetches data from external service"

    def test_count_correct(self):
        steps = [
            Step(line_number=i, type="decision", description="try/except block")
            for i in range(9)
        ]
        result = deduplicate_steps(steps)
        assert len(result) == 1
        assert len(result[0][1]) == 9

    def test_different_types_same_description_grouped(self):
        """Steps whose translate_step() output is identical get grouped."""
        steps = [
            _step("transform", "list comprehension: ..."),
            Step(line_number=2, type="transform", description="list comprehension: ..."),
        ]
        result = deduplicate_steps(steps)
        assert len(result) == 1
        assert len(result[0][1]) == 2

    def test_nine_try_except_scenario(self):
        """The motivating use case: 9x 'Handles potential errors'."""
        steps = [
            Step(line_number=i * 10, type="decision", description=f"try/except {i}")
            for i in range(1, 10)
        ]
        result = deduplicate_steps(steps)
        assert len(result) == 1
        desc, group = result[0]
        assert desc == "Handles potential errors"
        assert len(group) == 9

    def test_try_except_with_unique_interspersed(self):
        steps = [
            Step(line_number=1, type="decision", description="try/except a"),
            _step("api_call", "requests.get()"),
            Step(line_number=3, type="decision", description="try/except b"),
            _step("file_io", "json.dump()"),
            Step(line_number=5, type="decision", description="try/except c"),
        ]
        result = deduplicate_steps(steps)
        assert len(result) == 3
        assert result[0][0] == "Handles potential errors"
        assert len(result[0][1]) == 3
