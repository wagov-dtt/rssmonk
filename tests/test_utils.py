import hashlib
import unittest

from rssmonk.types import Frequency
from rssmonk.utils import extract_feed_hash, find_highest_frequency, make_filter_url, numberfy_subbed_lists, remove_other_keys

"""
Curated generated tests for the utils class for sanity checks
"""

class TestRemoveOtherKeys(unittest.TestCase):
    def test_key_present(self):
        self.assertEqual(remove_other_keys({'a': 1, 'b': 2}, 'a'), {'a': 1})

    def test_key_not_present(self):
        self.assertEqual(remove_other_keys({'a': 1, 'b': 2}, 'c'), {})

    def test_empty_dict(self):
        self.assertEqual(remove_other_keys({}, 'a'), {})

    def test_single_key_match(self):
        self.assertEqual(remove_other_keys({'x': 42}, 'x'), {'x': 42})

    def test_single_key_no_match(self):
        self.assertEqual(remove_other_keys({'x': 42}, 'y'), {})


class TestNumberfySubbedLists(unittest.TestCase):
    def test_with_ids(self):
        input_data = [{"id": 1}, {"id": 2}, {"id": 3}]
        self.assertEqual(numberfy_subbed_lists(input_data), [1, 2, 3])

    def test_mixed_dicts(self):
        input_data = [{"id": 10}, {"name": "Alice"}, {"id": 20}]
        self.assertEqual(numberfy_subbed_lists(input_data), [10, 20])

    def test_no_ids(self):
        input_data = [{"name": "Bob"}, {"value": 42}]
        self.assertEqual(numberfy_subbed_lists(input_data), [])

    def test_empty_list(self):
        input_data = []
        self.assertEqual(numberfy_subbed_lists(input_data), [])


class TestMakeFilterUrl(unittest.TestCase):
    def test_list_input(self):
        data = [1]
        self.assertEqual(make_filter_url(data), "filter=1")

        data = [1, 2, 3, 4, 5]
        self.assertEqual(make_filter_url(data), "filter=1,2,3,4,5")

    def test_dict_input_single_key(self):
        data = {"type": [4, 5]}
        self.assertEqual(make_filter_url(data), "type=4,5")

    def test_dict_input_multiple_keys(self):
        data = {"type": [1, 2], "status": [3, 4]}
        self.assertEqual(make_filter_url(data), "type=1,2&status=3,4")

        data = {"type": [1, 2], "status": [3, 4], "item": [1, 2, 3]}
        self.assertEqual(make_filter_url(data), "type=1,2&status=3,4&item=1,2,3")

    def test_empty_list(self):
        data = []
        self.assertEqual(make_filter_url(data), "")

    def test_empty_dict(self):
        data = {}
        self.assertEqual(make_filter_url(data), "")

    def test_dict_with_non_list_values(self):
        data = {"type": [1], "invalid": "notalist"}
        self.assertEqual(make_filter_url(data), "type=1")

        data = {"invalid": "notalist"}
        self.assertEqual(make_filter_url(data), "")


class TestExtractFeedHash(unittest.TestCase):
    def test_hash_from_username(self):
        result = extract_feed_hash("user_12345", "http://example.com/feed")
        self.assertEqual(result, "12345")

    def test_hash_from_url(self):
        result = extract_feed_hash("not_an_expected_user_name", "http://example.com/feed")
        self.assertEqual(result, hashlib.sha256("http://example.com/feed".encode()).hexdigest())

    def test_no_hash_no_url(self):
        result = extract_feed_hash("not_an_expected_user_name")
        self.assertEqual(result, "")


class TestFindHighestFrequency(unittest.TestCase):
    def test_returns_none_when_list_empty(self):
        assert find_highest_frequency([]) is None

    def test_returns_instant_when_present(self):
        assert find_highest_frequency([Frequency.INSTANT, Frequency.DAILY]) == Frequency.INSTANT

    def test_returns_first_priority_order_agnostic(self):
        # Instant should always be returned
        assert find_highest_frequency([Frequency.DAILY, Frequency.INSTANT]) == Frequency.INSTANT

    def test_returns_daily_when_instant_is_not_present(self):
        assert find_highest_frequency([Frequency.DAILY]) == Frequency.DAILY
