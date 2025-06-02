import unittest
import csv
import os
import io # Need io for StringIO
import requests # Need requests for mocking RequestException
import time # Need time for mocking sleep
import datetime # Need datetime for mocking date.today()
import json # Need json module for dumps
import concurrent.futures # Need for mocking ThreadPoolExecutor
from unittest.mock import patch, mock_open, MagicMock, call # Import call for checking multiple calls

# Import functions and constants to be tested from AutoScraper.py
# Assuming AutoScraper.py is in the same directory or Python path
try:
    from AutoScraper import (
        load_cache,
        append_to_cache,
        write_cache,
        CACHE_HEADERS,
        CACHE_FILE,
        logger, # Import logger to use assertLogs
        get_proxy_from_file,
        extract_vehicle_info_from_json,
        extract_vehicle_info, # Function to test
        parse_html_content_to_json, # Called by extract_vehicle_info
        process_links_and_update_cache, # Function to test
        fetch_autotrader_data # Function to test
    )
    # Import utils that might need mocking if called directly or indirectly
    from AutoScraperUtil import parse_html_content, remove_duplicates_exclusions, transform_strings, cls, convert_km_to_double
except ImportError as e:
    # Handle case where the script might be run from a different structure
    print(f"ImportError: {e}. Make sure AutoScraper.py and AutoScraperUtil.py are accessible.")
    # Define dummy values to allow tests to be discovered, though they will fail
    load_cache = append_to_cache = write_cache = MagicMock()
    get_proxy_from_file = MagicMock()
    extract_vehicle_info_from_json = MagicMock()
    extract_vehicle_info = MagicMock()
    parse_html_content_to_json = MagicMock()
    process_links_and_update_cache = MagicMock()
    fetch_autotrader_data = MagicMock()
    parse_html_content = MagicMock()
    remove_duplicates_exclusions = MagicMock()
    transform_strings = MagicMock()
    cls = MagicMock()
    convert_km_to_double = MagicMock() # Add dummy for this too
    CACHE_HEADERS = []
    CACHE_FILE = "dummy_cache.csv"
    logger = MagicMock()


# --- Test Class for fetch_autotrader_data ---
# Patch dependencies used across multiple tests in this class
@patch('AutoScraper.remove_duplicates_exclusions', side_effect=lambda data, exclusions: data) # Simple pass-through mock
@patch('AutoScraper.get_proxy_from_file', return_value={})
@patch('requests.Session')
@patch('time.sleep', return_value=None)
@patch('concurrent.futures.ThreadPoolExecutor')
@patch('AutoScraper.transform_strings', side_effect=lambda x: [s.lower() for s in x]) # Simple lowercasing mock
class TestFetchAutotraderData(unittest.TestCase):

    # Mock parse_html_content separately for tests that need specific return values
    @patch('AutoScraper.parse_html_content')
    def test_parameter_cleaning_and_defaults(self, mock_parse_html, mock_transform, mock_executor_cls, mock_sleep, mock_session_cls, mock_get_proxy, mock_remove_dupes):
        """Test that input parameters are cleaned and defaults applied correctly before the API call."""
        # Configure mocks
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "SearchResultsDataJson": json.dumps({"maxPage": 1, "totalResultCount": 0}),
            "AdsHtml": ""
        }
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_cls.return_value = mock_session
        mock_parse_html.return_value = [] # Don't need specific parsed data here

        input_params = {
            "Make": "TestMake", "Model": "TestModel", "Proximity": "50",
            "PriceMin": 1000, "YearMin": "2010", "Address": "TestCity, ON",
            "IsUsed": True, "Exclusions": ["bad word1", "BAD WORD2"],
            "OdometerMin": 5000, "OdometerMax": None, "Trim": "Any", "Color": "",
            "Drivetrain": "awd", "Transmission": "MANUAL", "IsDamaged": "false",
            "BodyType": "Any", "NumberOfDoors": "4", "SeatingCapacity": ""
        }

        # Expected payload after cleaning and defaults (keys with None value are omitted)
        expected_payload = {
            "Address": "TestCity, ON", "Proximity": "50", "Make": "TestMake", "Model": "TestModel",
            "PriceMin": 1000, "PriceMax": 999999, "Skip": 0, "Top": 15,
            "IsNew": True, "IsUsed": True, "WithPhotos": True,
            "YearMax": "2050", "YearMin": "2010", "OdometerMin": 5000, "OdometerMax": None,
            "micrositeType": 1, "Drivetrain": "awd", "Transmissions": "MANUAL",
            "IsDamaged": False, "NumberOfDoors": 4
        }

        fetch_autotrader_data(input_params.copy())
        mock_transform.assert_called_once_with(["bad word1", "BAD WORD2"])
        mock_session.post.assert_called_once()
        args, kwargs = mock_session.post.call_args
        sent_payload = kwargs.get('json', {})
        self.assertDictEqual(sent_payload, expected_payload)

    @patch('AutoScraper.parse_html_content')
    def test_fetch_initial_only(self, mock_parse_html, mock_transform, mock_executor_cls, mock_sleep, mock_session_cls, mock_get_proxy, mock_remove_dupes):
        """Test fetch_autotrader_data with initial_fetch_only=True."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_search_results_data = {"maxPage": 5, "totalResultCount": 65}
        mock_response.json.return_value = {
            "SearchResultsDataJson": json.dumps(mock_search_results_data),
            "AdsHtml": "<html>Page 0 Ads</html>"
        }
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_cls.return_value = mock_session
        # Specific mock for this test
        mock_parse_html.return_value = [{"link": "page0_link1"}, {"link": "page0_link2"}]

        input_params = {"Make": "Test", "Model": "Initial"}
        result = fetch_autotrader_data(input_params.copy(), initial_fetch_only=True)

        mock_session.post.assert_called_once()
        args, kwargs = mock_session.post.call_args
        sent_payload = kwargs.get('json', {})
        self.assertEqual(sent_payload.get('Skip'), 0)
        mock_parse_html.assert_called_once_with("<html>Page 0 Ads</html>", [])
        expected_return = {
            'estimated_count': 65,
            'initial_results_html': [{"link": "page0_link1"}, {"link": "page0_link2"}],
            'max_page': 5
        }
        self.assertDictEqual(result, expected_return)
        mock_executor_cls.assert_not_called()
        mock_remove_dupes.assert_not_called()

    @patch('AutoScraper.parse_html_content')
    @patch('concurrent.futures.as_completed') # Patch as_completed specifically here
    def test_fetch_full_success_multiple_pages(self, mock_as_completed, mock_parse_html, mock_transform, mock_executor_cls, mock_sleep, mock_session_cls, mock_get_proxy, mock_remove_dupes):
        """Test full fetch across multiple pages using ThreadPoolExecutor."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # Rename parameter to avoid shadowing json module
        def mock_post_side_effect(url, json_payload, timeout):
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status = MagicMock()
            page = json_payload['Skip'] // 15
            search_data = {"maxPage": 3, "totalResultCount": 40}
            ads_html = f"<html>Ads Page {page}</html>"
            response.json.return_value = {
                "SearchResultsDataJson": json.dumps(search_data), # Use imported json module
                "AdsHtml": ads_html
            }
            return response
        mock_session.post.side_effect = mock_post_side_effect

        def mock_parse_side_effect(html_content, exclusions):
            if "Page 0" in html_content: return [{"link": "p0_link1"}]
            if "Page 1" in html_content: return [{"link": "p1_link1"}, {"link": "p1_link2"}]
            if "Page 2" in html_content: return [{"link": "p2_link1"}]
            return []
        mock_parse_html.side_effect = mock_parse_side_effect

        mock_executor_instance = MagicMock()
        mock_executor_cls.return_value.__enter__.return_value = mock_executor_instance

        future1 = MagicMock()
        future1.result.return_value = ([{"link": "p1_link1"}, {"link": "p1_link2"}], 3, {})
        future2 = MagicMock()
        future2.result.return_value = ([{"link": "p2_link1"}], 3, {})

        submitted_futures = {}
        def submit_side_effect(func, page, session):
            if page == 1:
                submitted_futures[future1] = page
                return future1
            if page == 2:
                submitted_futures[future2] = page
                return future2
            raise ValueError(f"Unexpected page submitted: {page}")
        mock_executor_instance.submit.side_effect = submit_side_effect

        mock_as_completed.return_value = iter([future1, future2])
        mock_executor_instance.future_to_page = {future1: 1, future2: 2}

        input_params = {"Make": "Test", "Model": "MultiPage", "Exclusions": ["exclude_me"]}
        results = fetch_autotrader_data(input_params.copy())

        mock_transform.assert_called_once_with(["exclude_me"])
        self.assertEqual(mock_session.post.call_count, 3)
        post_calls = mock_session.post.call_args_list
        self.assertEqual(post_calls[0][1]['json']['Skip'], 0)
        self.assertEqual(post_calls[1][1]['json']['Skip'], 15)
        self.assertEqual(post_calls[2][1]['json']['Skip'], 30)

        mock_parse_html.assert_has_calls([
            call("<html>Ads Page 0</html>", ["exclude_me"]),
            call("<html>Ads Page 1</html>", ["exclude_me"]),
            call("<html>Ads Page 2</html>", ["exclude_me"])
        ], any_order=True)

        mock_executor_cls.assert_called_once_with(max_workers=200)
        submit_calls = mock_executor_instance.submit.call_args_list
        self.assertEqual(len(submit_calls), 2)
        submitted_pages = sorted([c[0][1] for c in submit_calls])
        self.assertEqual(submitted_pages, [1, 2])

        expected_results = [{"link": "p0_link1"}, {"link": "p1_link1"}, {"link": "p1_link2"}, {"link": "p2_link1"}]
        self.assertCountEqual(results, expected_results)
        mock_remove_dupes.assert_called_once()
        args, kwargs = mock_remove_dupes.call_args
        self.assertCountEqual(args[0], expected_results)
        self.assertEqual(args[1], ["exclude_me"])


# --- Test Class for extract_vehicle_info ---
@patch('AutoScraper.get_proxy_from_file', return_value={"http": "mock_proxy", "https": "mock_proxy"})
class TestExtractVehicleInfo(unittest.TestCase):

    @patch('requests.Session')
    @patch('AutoScraper.parse_html_content_to_json', return_value={"mock": "json"})
    @patch('AutoScraper.extract_vehicle_info_from_json', return_value={"extracted": "data"})
    @patch('time.sleep', return_value=None)
    def test_extract_success_first_try(self, mock_sleep, mock_extract_json, mock_parse_html, mock_session_cls, mock_get_proxy):
        """Test successful data extraction on the first attempt."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html>Success</html>'
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session
        test_url = "http://example.com/vehicle1"
        result = extract_vehicle_info(test_url)
        mock_session_cls.assert_called_once()
        mock_session.headers.update.assert_called()
        mock_session.proxies.update.assert_called_with({"http": "mock_proxy", "https": "mock_proxy"})
        mock_session.get.assert_called_once_with(test_url, timeout=30)
        mock_response.raise_for_status.assert_called_once()
        mock_parse_html.assert_called_once_with('<html>Success</html>')
        mock_extract_json.assert_called_once_with({"mock": "json"})
        self.assertEqual(result, {"extracted": "data"})
        mock_sleep.assert_not_called()

    @patch('requests.Session')
    @patch('AutoScraper.parse_html_content_to_json', return_value={"mock": "json"})
    @patch('AutoScraper.extract_vehicle_info_from_json', return_value={"extracted": "data"})
    @patch('time.sleep', return_value=None)
    def test_extract_success_after_429_retry(self, mock_sleep, mock_extract_json, mock_parse_html, mock_session_cls, mock_get_proxy):
        """Test successful data extraction after one 429 retry."""
        mock_session = MagicMock()
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.text = 'Rate limited'
        mock_response_429.raise_for_status = MagicMock(side_effect=requests.exceptions.HTTPError("429 Client Error"))
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.text = '<html>Success</html>'
        mock_response_200.raise_for_status = MagicMock()
        mock_session.get.side_effect = [mock_response_429, mock_response_200]
        mock_session_cls.return_value = mock_session
        test_url = "http://example.com/vehicle_retry"
        result = extract_vehicle_info(test_url)
        self.assertEqual(mock_session.get.call_count, 2)
        mock_sleep.assert_called_once()
        mock_parse_html.assert_called_once_with('<html>Success</html>')
        mock_extract_json.assert_called_once_with({"mock": "json"})
        self.assertEqual(result, {"extracted": "data"})

    @patch('requests.Session')
    @patch('AutoScraper.parse_html_content_to_json', return_value={"mock": "json"})
    @patch('AutoScraper.extract_vehicle_info_from_json', return_value={"extracted": "data"})
    @patch('time.sleep', return_value=None)
    def test_extract_success_after_text_retry(self, mock_sleep, mock_extract_json, mock_parse_html, mock_session_cls, mock_get_proxy):
        """Test successful data extraction after one text-based rate limit retry."""
        mock_session = MagicMock()
        mock_response_limit_text = MagicMock()
        mock_response_limit_text.status_code = 200
        mock_response_limit_text.text = 'Request unsuccessful.'
        mock_response_limit_text.raise_for_status = MagicMock()
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.text = '<html>Success</html>'
        mock_response_200.raise_for_status = MagicMock()
        mock_session.get.side_effect = [mock_response_limit_text, mock_response_200]
        mock_session_cls.return_value = mock_session
        test_url = "http://example.com/vehicle_retry_text"
        result = extract_vehicle_info(test_url)
        self.assertEqual(mock_session.get.call_count, 2)
        mock_sleep.assert_called_once()
        mock_parse_html.assert_called_once_with('<html>Success</html>')
        mock_extract_json.assert_called_once_with({"mock": "json"})
        self.assertEqual(result, {"extracted": "data"})

    @patch('requests.Session')
    @patch('time.sleep', return_value=None)
    def test_extract_failure_max_retries_429(self, mock_sleep, mock_session_cls, mock_get_proxy):
        """Test failure after max retries due to persistent 429."""
        mock_session = MagicMock()
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.text = 'Rate limited'
        mock_response_429.raise_for_status = MagicMock(side_effect=requests.exceptions.HTTPError("429 Client Error"))
        mock_session.get.return_value = mock_response_429
        mock_session_cls.return_value = mock_session
        test_url = "http://example.com/vehicle_fail_429"
        # The function catches the final Exception after retries
        with self.assertLogs(logger, level='ERROR') as log_cm:
             result = extract_vehicle_info(test_url)
             self.assertEqual(result, {})
             # Check for the "Unexpected error" log message which wraps the final exception message
             self.assertTrue(any("Unexpected error for http://example.com/vehicle_fail_429: Rate limited: HTTP 429 Too Many Requests." in msg for msg in log_cm.output))
        self.assertEqual(mock_session.get.call_count, 12)
        self.assertEqual(mock_sleep.call_count, 11)

    @patch('requests.Session')
    @patch('time.sleep', return_value=None)
    def test_extract_failure_request_exception(self, mock_sleep, mock_session_cls, mock_get_proxy):
        """Test failure due to a requests.exceptions.RequestException."""
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.RequestException("Connection failed")
        mock_session_cls.return_value = mock_session
        test_url = "http://example.com/vehicle_req_ex"
        with self.assertLogs(logger, level='ERROR') as log_cm:
            result = extract_vehicle_info(test_url)
            self.assertEqual(result, {})
            self.assertTrue(any("HTTP error for http://example.com/vehicle_req_ex: Connection failed" in msg for msg in log_cm.output))
        mock_session.get.assert_called_once()
        mock_sleep.assert_not_called()

    @patch('requests.Session')
    @patch('AutoScraper.parse_html_content_to_json', side_effect=ValueError("Invalid HTML"))
    @patch('time.sleep', return_value=None)
    def test_extract_failure_parsing_exception(self, mock_sleep, mock_parse_html, mock_session_cls, mock_get_proxy):
        """Test failure due to an exception during parsing (simulated as ValueError)."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html>Invalid</html>'
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session
        test_url = "http://example.com/vehicle_parse_err"
        with self.assertLogs(logger, level='ERROR') as log_cm:
            result = extract_vehicle_info(test_url)
            self.assertEqual(result, {})
            self.assertTrue(any("Unexpected error for http://example.com/vehicle_parse_err: Invalid HTML" in msg for msg in log_cm.output))
        mock_session.get.assert_called_once()
        mock_parse_html.assert_called_once_with('<html>Invalid</html>')
        mock_sleep.assert_not_called()


# --- Test Class for process_links_and_update_cache ---
@patch('AutoScraper.write_cache')
@patch('AutoScraper.extract_vehicle_info')
@patch('AutoScraper.load_cache')
@patch('datetime.date')
class TestProcessLinksAndUpdateCache(unittest.TestCase):

    def test_all_cache_miss(self, mock_date, mock_load_cache, mock_extract_info, mock_write_cache):
        """Test processing when all links are new (cache miss)."""
        test_today = datetime.date(2024, 1, 16)
        mock_date.today.return_value = test_today
        today_iso = test_today.isoformat()

        mock_load_cache.return_value = {}
        def mock_extract_side_effect(url):
            if url == "http://link1.com": return {"Make": "Make1", "Model": "Model1", "Year": "2021"}
            elif url == "http://link2.com": return {"Make": "Make2", "Model": "Model2", "Year": "2022"}
            return {}
        mock_extract_info.side_effect = mock_extract_side_effect
        input_links = [{"link": "http://link1.com"}, {"link": "http://link2.com"}]
        headers = CACHE_HEADERS if CACHE_HEADERS else ["Link", "Make", "Model", "Year", "date_cached"]
        expected_result_data = [ {header: "" for header in headers}, {header: "" for header in headers} ]
        expected_result_data[0].update({"Link": "http://link1.com", "Make": "Make1", "Model": "Model1", "Year": "2021", "date_cached": today_iso})
        expected_result_data[1].update({"Link": "http://link2.com", "Make": "Make2", "Model": "Model2", "Year": "2022", "date_cached": today_iso})
        expected_written_cache = { "http://link1.com": expected_result_data[0], "http://link2.com": expected_result_data[1] }
        result = process_links_and_update_cache(input_links, max_workers=1)
        mock_load_cache.assert_called_once()
        mock_extract_info.assert_has_calls([call("http://link1.com"), call("http://link2.com")], any_order=True)
        self.assertEqual(mock_extract_info.call_count, 2)
        mock_write_cache.assert_called_once_with(expected_written_cache)
        self.assertCountEqual(result, expected_result_data)

    def test_all_cache_hit_fresh(self, mock_date, mock_load_cache, mock_extract_info, mock_write_cache):
        """Test processing when all links are fresh cache hits."""
        test_today = datetime.date(2024, 1, 16)
        mock_date.today.return_value = test_today
        today_iso = test_today.isoformat()

        headers = CACHE_HEADERS if CACHE_HEADERS else ["Link", "Make", "Model", "date_cached"]
        initial_cache = {
            "http://link1.com": {"Link": "http://link1.com", "Make": "Make1", "Model": "Model1", "date_cached": today_iso},
            "http://link2.com": {"Link": "http://link2.com", "Make": "Make2", "Model": "Model2", "date_cached": today_iso}
        }
        full_initial_cache = {}
        for link, data in initial_cache.items(): full_initial_cache[link] = {header: data.get(header, "") for header in headers}
        mock_load_cache.return_value = full_initial_cache
        input_links = [{"link": "http://link1.com"}, {"link": "http://link2.com"}]
        expected_result_data = list(full_initial_cache.values())
        result = process_links_and_update_cache(input_links, max_workers=1)
        mock_load_cache.assert_called_once()
        mock_extract_info.assert_not_called()
        mock_write_cache.assert_called_once_with(full_initial_cache)
        self.assertCountEqual(result, expected_result_data)

    def test_all_cache_hit_stale(self, mock_date, mock_load_cache, mock_extract_info, mock_write_cache):
        """Test processing when all links are stale cache hits (need refresh)."""
        test_today = datetime.date(2024, 1, 16)
        mock_date.today.return_value = test_today
        today_iso = test_today.isoformat()
        yesterday_iso = "2024-01-15"

        headers = CACHE_HEADERS if CACHE_HEADERS else ["Link", "Make", "Model", "Year", "date_cached"]
        initial_cache = {
            "http://link1.com": {"Link": "http://link1.com", "Make": "OldMake1", "Model": "OldModel1", "date_cached": yesterday_iso},
            "http://link2.com": {"Link": "http://link2.com", "Make": "OldMake2", "Model": "OldModel2", "date_cached": yesterday_iso}
        }
        full_initial_cache = {}
        for link, data in initial_cache.items(): full_initial_cache[link] = {header: data.get(header, "") for header in headers}
        mock_load_cache.return_value = full_initial_cache
        def mock_extract_side_effect(url):
            if url == "http://link1.com": return {"Make": "NewMake1", "Model": "NewModel1", "Year": "2023"}
            elif url == "http://link2.com": return {"Make": "NewMake2", "Model": "NewModel2", "Year": "2024"}
            return {}
        mock_extract_info.side_effect = mock_extract_side_effect
        input_links = [{"link": "http://link1.com"}, {"link": "http://link2.com"}]
        expected_result_data = [ {header: "" for header in headers}, {header: "" for header in headers} ]
        expected_result_data[0].update({"Link": "http://link1.com", "Make": "NewMake1", "Model": "NewModel1", "Year": "2023", "date_cached": today_iso})
        expected_result_data[1].update({"Link": "http://link2.com", "Make": "NewMake2", "Model": "NewModel2", "Year": "2024", "date_cached": today_iso})
        expected_written_cache = { "http://link1.com": expected_result_data[0], "http://link2.com": expected_result_data[1] }
        result = process_links_and_update_cache(input_links, max_workers=1)
        mock_load_cache.assert_called_once()
        mock_extract_info.assert_has_calls([call("http://link1.com"), call("http://link2.com")], any_order=True)
        self.assertEqual(mock_extract_info.call_count, 2)
        mock_write_cache.assert_called_once_with(expected_written_cache)
        self.assertCountEqual(result, expected_result_data)

    def test_mixed_cache_hits_misses(self, mock_date, mock_load_cache, mock_extract_info, mock_write_cache):
        """Test processing with a mix of fresh, stale, and new links."""
        test_today = datetime.date(2024, 1, 16)
        mock_date.today.return_value = test_today
        today_iso = test_today.isoformat()
        yesterday_iso = "2024-01-15"

        headers = CACHE_HEADERS if CACHE_HEADERS else ["Link", "Make", "Model", "Year", "date_cached"]
        initial_cache = {
            "http://fresh.com": {"Link": "http://fresh.com", "Make": "FreshMake", "Model": "FreshModel", "date_cached": today_iso},
            "http://stale.com": {"Link": "http://stale.com", "Make": "OldStaleMake", "Model": "OldStaleModel", "date_cached": yesterday_iso}
        }
        full_initial_cache = {}
        for link, data in initial_cache.items(): full_initial_cache[link] = {header: data.get(header, "") for header in headers}
        mock_load_cache.return_value = full_initial_cache
        def mock_extract_side_effect(url):
            if url == "http://stale.com": return {"Make": "NewStaleMake", "Model": "NewStaleModel", "Year": "2022"}
            elif url == "http://new.com": return {"Make": "NewMake", "Model": "NewModel", "Year": "2023"}
            return {}
        mock_extract_info.side_effect = mock_extract_side_effect
        input_links = [ {"link": "http://fresh.com"}, {"link": "http://stale.com"}, {"link": "http://new.com"} ]
        fresh_data = full_initial_cache["http://fresh.com"]
        refreshed_stale_data = {header: "" for header in headers}
        refreshed_stale_data.update({"Link": "http://stale.com", "Make": "NewStaleMake", "Model": "NewStaleModel", "Year": "2022", "date_cached": today_iso})
        new_data = {header: "" for header in headers}
        new_data.update({"Link": "http://new.com", "Make": "NewMake", "Model": "NewModel", "Year": "2023", "date_cached": today_iso})
        expected_result_data = [fresh_data, refreshed_stale_data, new_data]
        expected_written_cache = { "http://fresh.com": fresh_data, "http://stale.com": refreshed_stale_data, "http://new.com": new_data }
        result = process_links_and_update_cache(input_links, max_workers=1)
        mock_load_cache.assert_called_once()
        mock_extract_info.assert_has_calls([call("http://stale.com"), call("http://new.com")], any_order=True)
        self.assertEqual(mock_extract_info.call_count, 2) # Correct assertion
        mock_write_cache.assert_called_once_with(expected_written_cache)
        self.assertCountEqual(result, expected_result_data)


# --- Test Class for extract_vehicle_info_from_json ---
class TestExtractVehicleInfoFromJson(unittest.TestCase):

    @patch('AutoScraper.convert_km_to_double', return_value=12345.0)
    def test_extract_full_data(self, mock_convert_km):
        """Test extracting data from a complete JSON structure."""
        mock_json = {
            "HeroViewModel": { "Make": "Honda", "Model": "Civic", "Trim": "Touring", "Price": "30000", "mileage": "12,345 km", "drivetrain": "FWD", "Year": "2022" },
            "Specifications": { "Specs": [
                    {"Key": "Kilometres", "Value": "12,345 km"}, {"Key": "Status", "Value": "Used"}, {"Key": "Trim", "Value": "Touring"},
                    {"Key": "Body Type", "Value": "Sedan"}, {"Key": "Engine", "Value": "1.5L I-4"}, {"Key": "Cylinder", "Value": "4"},
                    {"Key": "Transmission", "Value": "CVT"}, {"Key": "Drivetrain", "Value": "FWD"}, {"Key": "Exterior Colour", "Value": "White"},
                    {"Key": "Doors", "Value": "4"}, {"Key": "Fuel Type", "Value": "Gasoline"}, {"Key": "City Fuel Economy", "Value": "7.6 L/100km"},
                    {"Key": "Hwy Fuel Economy", "Value": "6.1 L/100km"} ] }
        }
        expected_info = {
            "Make": "Honda", "Model": "Civic", "Trim": "Touring", "Price": "30000", "Kilometres": 12345.0, "Drivetrain": "FWD", "Year": "2022",
            "Status": "Used", "Body Type": "Sedan", "Engine": "1.5L I-4", "Cylinder": "4", "Transmission": "CVT", "Exterior Colour": "White",
            "Doors": "4", "Fuel Type": "Gasoline", "City Fuel Economy": "7.6 ", "Hwy Fuel Economy": "6.1 "
        }
        result = extract_vehicle_info_from_json(mock_json)
        all_required_keys = list(expected_info.keys())
        for key in all_required_keys:
            if result.get(key) is None: result[key] = ""
            elif key not in result: result[key] = ""
        self.assertEqual(result, expected_info)
        mock_convert_km.assert_called_once_with("12,345 km")

    @patch('AutoScraper.convert_km_to_double', return_value=0.0)
    def test_extract_missing_data(self, mock_convert_km):
        """Test extracting data when some keys or sections are missing."""
        mock_json = {
            "HeroViewModel": { "Make": "Toyota", "Model": "Corolla", "Trim": "LE", "Price": "24000" },
            "Specifications": { "Specs": [ {"Key": "Kilometres", "Value": "N/A"}, {"Key": "Status", "Value": "New"}, {"Key": "Body Type", "Value": "Sedan"}, {"Key": "Transmission", "Value": "Automatic"}, ] }
        }
        expected_info = {
            "Make": "Toyota", "Model": "Corolla", "Trim": "LE", "Price": "24000", "Kilometres": 0.0, "Drivetrain": "", "Year": "",
            "Status": "New", "Body Type": "Sedan", "Engine": "", "Cylinder": "", "Transmission": "Automatic", "Exterior Colour": "",
            "Doors": "", "Fuel Type": "", "City Fuel Economy": "", "Hwy Fuel Economy": ""
        }
        result = extract_vehicle_info_from_json(mock_json)
        all_required_keys = list(expected_info.keys())
        for key in all_required_keys:
            if result.get(key) is None: result[key] = ""
            elif key not in result: result[key] = ""
        self.assertEqual(result, expected_info)
        mock_convert_km.assert_called_once_with("N/A")

    @patch('AutoScraper.convert_km_to_double', return_value=0.0)
    def test_extract_empty_specs(self, mock_convert_km):
        """Test extracting data when Specifications or Specs list is empty/missing."""
        mock_json_no_specs_list = { "HeroViewModel": {"Make": "Ford", "Model": "F-150", "Year": "2021"}, "Specifications": {} }
        mock_json_empty_specs_list = { "HeroViewModel": {"Make": "Ford", "Model": "F-150", "Year": "2021"}, "Specifications": {"Specs": []} }
        mock_json_no_specifications = { "HeroViewModel": {"Make": "Ford", "Model": "F-150", "Year": "2021"} }
        expected_partial_info = {
            "Make": "Ford", "Model": "F-150", "Trim": "", "Price": "", "Kilometres": "", "Drivetrain": "", "Year": "2021",
            "Status": "", "Body Type": "", "Engine": "", "Cylinder": "", "Transmission": "", "Exterior Colour": "", "Doors": "",
            "Fuel Type": "", "City Fuel Economy": "", "Hwy Fuel Economy": ""
        }
        all_required_keys = list(expected_partial_info.keys())
        result1 = extract_vehicle_info_from_json(mock_json_no_specs_list)
        for key in all_required_keys:
             if result1.get(key) is None: result1[key] = ""
             elif key not in result1: result1[key] = ""
        self.assertEqual(result1, expected_partial_info)
        result2 = extract_vehicle_info_from_json(mock_json_empty_specs_list)
        for key in all_required_keys:
             if result2.get(key) is None: result2[key] = ""
             elif key not in result2: result2[key] = ""
        self.assertEqual(result2, expected_partial_info)
        result3 = extract_vehicle_info_from_json(mock_json_no_specifications)
        for key in all_required_keys:
             if result3.get(key) is None: result3[key] = ""
             elif key not in result3: result3[key] = ""
        self.assertEqual(result3, expected_partial_info)
        mock_convert_km.assert_not_called()

    def test_extract_empty_input(self):
        """Test extracting data from empty or None input."""
        self.assertEqual(extract_vehicle_info_from_json(None), {})
        self.assertEqual(extract_vehicle_info_from_json({}), {})

# --- Test Class for get_proxy_from_file ---
class TestProxyFunction(unittest.TestCase):

    def test_get_proxy_success(self):
        """Test successfully loading proxy data from a JSON file."""
        mock_json_data = '{"http": "http://user:pass@10.10.1.10:3128", "https": "https://user:pass@10.10.1.10:1080"}'
        expected_proxy = {"http": "http://user:pass@10.10.1.10:3128", "https": "https://user:pass@10.10.1.10:1080"}
        with patch("builtins.open", mock_open(read_data=mock_json_data)) as mocked_open:
            proxy = get_proxy_from_file("dummy_proxy.json")
            mocked_open.assert_called_once_with("dummy_proxy.json", 'r')
            self.assertEqual(proxy, expected_proxy)

    def test_get_proxy_file_not_found(self):
        """Test get_proxy_from_file when the proxy file does not exist."""
        with patch("builtins.open", mock_open()) as mocked_open:
            mocked_open.side_effect = FileNotFoundError
            result = get_proxy_from_file("non_existent_proxy.json")
            self.assertEqual(result, "File 'non_existent_proxy.json' not found.")

    def test_get_proxy_invalid_json(self):
        """Test get_proxy_from_file with invalid JSON content."""
        mock_invalid_json_data = '{"http": "http://proxy", "https":}'
        with patch("builtins.open", mock_open(read_data=mock_invalid_json_data)) as mocked_open:
            result = get_proxy_from_file("invalid_proxy.json")
            self.assertEqual(result, "Invalid JSON format.")

# --- Test Class for Cache Functions ---
class TestCacheFunctions(unittest.TestCase):

    def test_load_cache_file_not_found(self):
        """Test load_cache when the cache file does not exist."""
        with patch("builtins.open", mock_open()) as mocked_open:
            mocked_open.side_effect = FileNotFoundError
            with self.assertLogs(logger, level='INFO') as log_cm:
                cache = load_cache("non_existent_cache.csv")
                self.assertEqual(cache, {})
                self.assertTrue(any("Cache file 'non_existent_cache.csv' not found" in msg for msg in log_cm.output))

    def test_load_cache_success(self):
        """Test successfully loading data from a cache file."""
        mock_csv_content = (
            "Link,Make,Model,Year,Trim,Price,Drivetrain,Kilometres,Status,Body Type,Engine,Cylinder,Transmission,Exterior Colour,Doors,Fuel Type,City Fuel Economy,Hwy Fuel Economy,date_cached\n"
            "http://example.com/1,Toyota,Camry,2020,LE,25000,FWD,15000,Used,Sedan,2.5L,4,Auto,Red,4,Gas,8.0,6.0,2024-01-15\n"
            "http://example.com/2,Honda,Civic,2021,LX,22000,FWD,10000,Used,Sedan,1.5L,4,CVT,Blue,4,Gas,7.5,5.5,2024-01-15\n"
        )
        expected_cache = {
            "http://example.com/1": { "Link": "http://example.com/1", "Make": "Toyota", "Model": "Camry", "Year": "2020", "Trim": "LE", "Price": "25000", "Drivetrain": "FWD", "Kilometres": "15000", "Status": "Used", "Body Type": "Sedan", "Engine": "2.5L", "Cylinder": "4", "Transmission": "Auto", "Exterior Colour": "Red", "Doors": "4", "Fuel Type": "Gas", "City Fuel Economy": "8.0", "Hwy Fuel Economy": "6.0", "date_cached": "2024-01-15" },
            "http://example.com/2": { "Link": "http://example.com/2", "Make": "Honda", "Model": "Civic", "Year": "2021", "Trim": "LX", "Price": "22000", "Drivetrain": "FWD", "Kilometres": "10000", "Status": "Used", "Body Type": "Sedan", "Engine": "1.5L", "Cylinder": "4", "Transmission": "CVT", "Exterior Colour": "Blue", "Doors": "4", "Fuel Type": "Gas", "City Fuel Economy": "7.5", "Hwy Fuel Economy": "5.5", "date_cached": "2024-01-15" }
        }
        # Use mock_open correctly with DictReader
        m_open = mock_open(read_data=mock_csv_content)
        with patch("builtins.open", m_open):
             # Simulate DictReader consuming the handle provided by mock_open
             # Correctly simulate DictReader by passing the file handle from mock_open
             with patch("csv.DictReader", lambda f, *args, **kwargs: csv.DictReader(f, *args, **kwargs)) as mock_csv_reader:
                 with self.assertLogs(logger, level='INFO') as log_cm:
                     cache = load_cache("dummy_cache.csv")
                     self.assertEqual(cache, expected_cache)
                     self.assertTrue(any("Loaded 2 items" in msg for msg in log_cm.output))

    def test_load_cache_header_mismatch(self):
        """Test loading a cache file with mismatched headers."""
        mock_csv_content = "Link,Make,Model,Year,Price,date_cached\nhttp://example.com/1,Toyota,Camry,2020,25000,2024-01-15\n"
        expected_loaded_dict = { "http://example.com/1": { "Link": "http://example.com/1", "Make": "Toyota", "Model": "Camry", "Year": "2020", "Price": "25000", "date_cached": "2024-01-15" } }
        m_open = mock_open(read_data=mock_csv_content)
        with patch("builtins.open", m_open):
             # Simulate DictReader consuming the handle provided by mock_open
             with patch("csv.DictReader", lambda f, *args, **kwargs: csv.DictReader(f, *args, **kwargs)) as mock_csv_reader:
                 with self.assertLogs(logger, level='WARNING') as log_cm:
                     cache = load_cache("dummy_cache.csv")
                     # Check warning log *before* asserting equality
                     self.assertTrue(any("headers mismatch expected headers" in msg for msg in log_cm.output))
                     self.assertEqual(cache, expected_loaded_dict) # Asserts the actual loaded dict

    @patch('os.path.isfile')
    @patch('os.path.getsize')
    def test_append_to_cache_new_file(self, mock_getsize, mock_isfile):
        """Test appending data to a new cache file (writes header)."""
        mock_isfile.return_value = False
        mock_getsize.return_value = 0
        data_to_append = [ {"Link": "http://test.com/a", "Make": "TestMake", "Model": "TestModel", "Year": "2023", "date_cached": "2024-01-16"} ]
        headers_to_use = CACHE_HEADERS if CACHE_HEADERS else list(data_to_append[0].keys())
        full_data_row = {header: data_to_append[0].get(header, "") for header in headers_to_use}
        m = mock_open()
        with patch("builtins.open", m):
            with self.assertLogs(logger, level='INFO') as log_cm:
                append_to_cache(data_to_append, "new_cache.csv", headers_to_use)
                m.assert_called_once_with("new_cache.csv", mode='a', newline='', encoding='utf-8')
                handle = m()
                handle.write.assert_any_call(",".join(headers_to_use) + "\r\n")
                expected_row_string = ",".join([full_data_row[h] for h in headers_to_use]) + "\r\n"
                handle.write.assert_any_call(expected_row_string)
                self.assertTrue(any("Created or wrote headers to cache file" in msg for msg in log_cm.output))
                self.assertTrue(any("Appended 1 new items" in msg for msg in log_cm.output))

    @patch('os.path.isfile')
    @patch('os.path.getsize')
    def test_append_to_cache_existing_file(self, mock_getsize, mock_isfile):
        """Test appending data to an existing cache file (no header)."""
        mock_isfile.return_value = True
        mock_getsize.return_value = 100
        data_to_append = [ {"Link": "http://test.com/b", "Make": "AnotherMake", "Model": "AnotherModel", "Year": "2022", "date_cached": "2024-01-16"} ]
        headers_to_use = CACHE_HEADERS if CACHE_HEADERS else list(data_to_append[0].keys())
        full_data_row = {header: data_to_append[0].get(header, "") for header in headers_to_use}
        m = mock_open()
        with patch("builtins.open", m):
             with self.assertLogs(logger, level='INFO') as log_cm:
                append_to_cache(data_to_append, "existing_cache.csv", headers_to_use)
                m.assert_called_once_with("existing_cache.csv", mode='a', newline='', encoding='utf-8')
                handle = m()
                header_string = ",".join(headers_to_use) + "\r\n"
                # Corrected access to call args
                write_calls = [call_args[0][0] for call_args in handle.write.call_args_list]
                self.assertNotIn(header_string, write_calls)
                expected_row_string = ",".join([full_data_row[h] for h in headers_to_use]) + "\r\n"
                handle.write.assert_any_call(expected_row_string)
                self.assertTrue(any("Appended 1 new items" in msg for msg in log_cm.output))
                self.assertFalse(any("Created or wrote headers" in msg for msg in log_cm.output))

    def test_write_cache(self):
        """Test writing the entire cache dictionary to a file."""
        cache_to_write = { "http://example.com/1": { "Link": "http://example.com/1", "Make": "Toyota", "Model": "Camry", "Year": "2020", "Trim": "LE", "Price": "25000", "Drivetrain": "FWD", "Kilometres": "15000", "Status": "Used", "Body Type": "Sedan", "Engine": "2.5L", "Cylinder": "4", "Transmission": "Auto", "Exterior Colour": "Red", "Doors": "4", "Fuel Type": "Gas", "City Fuel Economy": "8.0", "Hwy Fuel Economy": "6.0", "date_cached": "2024-01-15" } }
        headers_to_use = CACHE_HEADERS if CACHE_HEADERS else list(cache_to_write["http://example.com/1"].keys())
        row1_dict = {header: cache_to_write["http://example.com/1"].get(header, "") for header in headers_to_use}
        m = mock_open()
        with patch("builtins.open", m):
            with self.assertLogs(logger, level='INFO') as log_cm:
                write_cache(cache_to_write, "output_cache.csv", headers_to_use)
                m.assert_called_once_with("output_cache.csv", mode='w', newline='', encoding='utf-8')
                handle = m()
                handle.write.assert_any_call(",".join(headers_to_use) + "\r\n")
                expected_row1_string = ",".join([row1_dict[h] for h in headers_to_use]) + "\r\n"
                handle.write.assert_any_call(expected_row1_string)
                self.assertTrue(any("Wrote 1 items to cache file" in msg for msg in log_cm.output))

if __name__ == '__main__':
    unittest.main()
