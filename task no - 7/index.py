from __future__ import annotations
 
from unittest.mock import MagicMock, patch
 
import pytest
import requests
 
from data_processor import (
    DataExtractionError,
    DataProcessor,
    DataValidationError,
    Record,
    fetch_data_from_api,
    parse_record,
    parse_records,
    parse_records_lenient,
)
 
 
# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def endpoint() -> str:
    """A fake API endpoint used across tests -- never actually hit the network."""
    return "https://api.example.com/records"
 
 
@pytest.fixture
def valid_raw_records():
    """A realistic batch of valid raw API records."""
    return [
        {"id": 1, "name": "Widget", "value": 9.99, "active": True},
        {"id": 2, "name": "Gadget", "value": 19.99, "active": False},
        {"id": "3", "name": "Gizmo", "value": "5.5"},  # coercible types, active defaults True
    ]
 
 
@pytest.fixture
def mixed_raw_records(valid_raw_records):
    """Valid records plus a few invalid ones, for lenient-parsing tests."""
    invalid = [
        {"id": 4, "name": "", "value": 1.0},          # blank name
        {"id": "abc", "name": "BadId", "value": 1.0},  # non-numeric id
        {"name": "NoId", "value": 1.0},                # missing id
    ]
    return valid_raw_records + invalid
 
 
def _make_mock_response(json_data=None, status_code=200, raise_json_error=False):
    """Helper to build a MagicMock standing in for a `requests.Response`."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    if raise_json_error:
        mock_response.json.side_effect = ValueError("No JSON could be decoded")
    else:
        mock_response.json.return_value = json_data
    return mock_response
 
 
@pytest.fixture
def mock_api_success(valid_raw_records):
    
    with patch("data_processor.requests.get") as mock_get:
        mock_get.return_value = _make_mock_response(json_data=valid_raw_records)
        yield mock_get
 
 
# --------------------------------------------------------------------------- #
# fetch_data_from_api -- extraction tests
# --------------------------------------------------------------------------- #
class TestFetchDataFromApi:
    def test_returns_parsed_json_on_success(self, endpoint, valid_raw_records):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=valid_raw_records)
 
            result = fetch_data_from_api(endpoint)
 
            assert result == valid_raw_records
            mock_get.assert_called_once_with(endpoint, timeout=10)
 
    def test_passes_custom_timeout(self, endpoint, valid_raw_records):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=valid_raw_records)
 
            fetch_data_from_api(endpoint, timeout=30)
 
            mock_get.assert_called_once_with(endpoint, timeout=30)
 
    def test_empty_list_response_is_valid(self, endpoint):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=[])
 
            result = fetch_data_from_api(endpoint)
 
            assert result == []
 
    def test_raises_on_non_200_status(self, endpoint):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=[], status_code=500)
 
            with pytest.raises(DataExtractionError, match="non-200 status code"):
                fetch_data_from_api(endpoint)
 
    def test_raises_on_404(self, endpoint):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=[], status_code=404)
 
            with pytest.raises(DataExtractionError, match="404"):
                fetch_data_from_api(endpoint)
 
    def test_raises_on_invalid_json(self, endpoint):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(raise_json_error=True)
 
            with pytest.raises(DataExtractionError, match="not valid JSON"):
                fetch_data_from_api(endpoint)
 
    def test_raises_when_json_is_not_a_list(self, endpoint):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data={"not": "a list"})
 
            with pytest.raises(DataExtractionError, match="must be a list"):
                fetch_data_from_api(endpoint)
 
    def test_raises_on_timeout(self, endpoint):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()
 
            with pytest.raises(DataExtractionError, match="timed out"):
                fetch_data_from_api(endpoint)
 
    def test_raises_on_connection_error(self, endpoint):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("refused")
 
            with pytest.raises(DataExtractionError, match="failed"):
                fetch_data_from_api(endpoint)
 
    def test_no_real_network_call_is_ever_made(self, endpoint, mock_api_success):
        """Sanity check that the suite is fully offline/deterministic."""
        fetch_data_from_api(endpoint)
        # requests.get has been replaced by the fixture's mock, so this
        # call could not possibly have touched the real network.
        assert mock_api_success.called
        assert isinstance(mock_api_success, MagicMock)
 
 
# --------------------------------------------------------------------------- #
# parse_record / parse_records -- parsing tests
# --------------------------------------------------------------------------- #
class TestParseRecord:
    def test_parses_valid_record(self):
        raw = {"id": 1, "name": "Widget", "value": 9.99, "active": True}
 
        record = parse_record(raw)
 
        assert record == Record(id=1, name="Widget", value=9.99, active=True)
 
    def test_coerces_string_id_and_value(self):
        raw = {"id": "42", "name": "Thing", "value": "3.14"}
 
        record = parse_record(raw)
 
        assert record.id == 42
        assert record.value == pytest.approx(3.14)
 
    def test_defaults_active_to_true_when_missing(self):
        raw = {"id": 1, "name": "Widget", "value": 1.0}
 
        record = parse_record(raw)
 
        assert record.active is True
 
    def test_strips_whitespace_from_name(self):
        raw = {"id": 1, "name": "  Widget  ", "value": 1.0}
 
        record = parse_record(raw)
 
        assert record.name == "Widget"
 
    @pytest.mark.parametrize("missing_field", ["id", "name", "value"])
    def test_raises_on_missing_required_field(self, missing_field):
        raw = {"id": 1, "name": "Widget", "value": 1.0}
        del raw[missing_field]
 
        with pytest.raises(DataValidationError, match="Missing required field"):
            parse_record(raw)
 
    def test_raises_on_non_dict_input(self):
        with pytest.raises(DataValidationError, match="must be a dict"):
            parse_record(["not", "a", "dict"])  # type: ignore[arg-type]
 
    def test_raises_on_invalid_id(self):
        raw = {"id": "not-a-number", "name": "Widget", "value": 1.0}
 
        with pytest.raises(DataValidationError, match="Invalid id"):
            parse_record(raw)
 
    def test_raises_on_blank_name(self):
        raw = {"id": 1, "name": "   ", "value": 1.0}
 
        with pytest.raises(DataValidationError, match="Invalid name"):
            parse_record(raw)
 
    def test_raises_on_non_string_name(self):
        raw = {"id": 1, "name": 12345, "value": 1.0}
 
        with pytest.raises(DataValidationError, match="Invalid name"):
            parse_record(raw)
 
    def test_raises_on_invalid_value(self):
        raw = {"id": 1, "name": "Widget", "value": "not-a-float"}
 
        with pytest.raises(DataValidationError, match="Invalid value"):
            parse_record(raw)
 
 
class TestParseRecords:
    def test_parses_all_valid_records(self, valid_raw_records):
        records = parse_records(valid_raw_records)
 
        assert len(records) == 3
        assert all(isinstance(r, Record) for r in records)
 
    def test_empty_list_returns_empty_list(self):
        assert parse_records([]) == []
 
    def test_strict_mode_raises_on_first_bad_record(self, valid_raw_records):
        bad_batch = valid_raw_records + [{"id": 1}]  # missing name/value
 
        with pytest.raises(DataValidationError):
            parse_records(bad_batch)
 
    def test_lenient_mode_skips_bad_records_and_collects_errors(self, mixed_raw_records):
        parsed, errors = parse_records_lenient(mixed_raw_records)
 
        assert len(parsed) == 3  # only the 3 originally-valid records
        assert len(errors) == 3
        assert all("Record at index" in e for e in errors)
 
    def test_lenient_mode_with_all_valid_records_has_no_errors(self, valid_raw_records):
        parsed, errors = parse_records_lenient(valid_raw_records)
 
        assert len(parsed) == len(valid_raw_records)
        assert errors == []
 
 
# --------------------------------------------------------------------------- #
# DataProcessor -- integration-style tests (extraction + parsing combined)
# --------------------------------------------------------------------------- #
class TestDataProcessor:
    def test_process_returns_parsed_records(self, endpoint, mock_api_success):
        processor = DataProcessor(endpoint)
 
        records = processor.process()
 
        assert len(records) == 3
        assert isinstance(records[0], Record)
        mock_api_success.assert_called_once_with(endpoint, timeout=10)
 
    def test_process_strict_raises_on_bad_data(self, endpoint):
        bad_data = [{"id": 1, "name": "Widget"}]  # missing value
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=bad_data)
 
            processor = DataProcessor(endpoint)
 
            with pytest.raises(DataValidationError):
                processor.process(strict=True)
 
    def test_process_lenient_skips_bad_data(self, endpoint, mixed_raw_records):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=mixed_raw_records)
 
            processor = DataProcessor(endpoint)
            records = processor.process(strict=False)
 
            assert len(records) == 3
 
    def test_process_propagates_extraction_errors(self, endpoint):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=[], status_code=503)
 
            processor = DataProcessor(endpoint)
 
            with pytest.raises(DataExtractionError):
                processor.process()
 
    def test_process_with_report_returns_records_and_errors(self, endpoint, mixed_raw_records):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=mixed_raw_records)
 
            processor = DataProcessor(endpoint)
            records, errors = processor.process_with_report()
 
            assert len(records) == 3
            assert len(errors) == 3
 
    def test_custom_timeout_is_used_for_extraction(self, endpoint, valid_raw_records):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=valid_raw_records)
 
            processor = DataProcessor(endpoint, timeout=5)
            processor.extract()
 
            mock_get.assert_called_once_with(endpoint, timeout=5)
 
 
class TestDataProcessorSummarize:
    def test_summarize_computes_correct_aggregates(self, endpoint):
        records = [
            Record(id=1, name="A", value=10.0, active=True),
            Record(id=2, name="B", value=20.0, active=False),
            Record(id=3, name="C", value=30.0, active=True),
        ]
        processor = DataProcessor(endpoint)
 
        summary = processor.summarize(records)
 
        assert summary["count"] == 3
        assert summary["active_count"] == 2
        assert summary["total_value"] == pytest.approx(60.0)
        assert summary["average_value"] == pytest.approx(20.0)
 
    def test_summarize_handles_empty_list(self, endpoint):
        processor = DataProcessor(endpoint)
 
        summary = processor.summarize([])
 
        assert summary == {
            "count": 0,
            "active_count": 0,
            "total_value": 0.0,
            "average_value": 0.0,
        }
 
    def test_summarize_defaults_to_calling_process_when_no_records_given(
        self, endpoint, mock_api_success
    ):
        processor = DataProcessor(endpoint)
 
        summary = processor.summarize()
 
        assert summary["count"] == 3
        mock_api_success.assert_called_once()
 
 
# --------------------------------------------------------------------------- #
# Isolation sanity checks
# --------------------------------------------------------------------------- #
class TestMockIsolation:
    def test_mock_does_not_leak_between_tests_1(self, endpoint):
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=[{"id": 1, "name": "X", "value": 1}])
            assert fetch_data_from_api(endpoint) == [{"id": 1, "name": "X", "value": 1}]
            assert mock_get.call_count == 1
 
    def test_mock_does_not_leak_between_tests_2(self, endpoint):
        # A fresh patch context each test means call_count always starts at 0.
        with patch("data_processor.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(json_data=[])
            fetch_data_from_api(endpoint)
            assert mock_get.call_count == 1
 