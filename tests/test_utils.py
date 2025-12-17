import hashlib
import unittest

from rssmonk.utils import expand_filter_identifiers, extract_feed_hash, make_filter_url, matches_filter, numberfy_subbed_lists

"""
Curated generated tests for the utils class for sanity checks
"""

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


class TestExpandFilterIdentifiers(unittest.TestCase):
    def test_empty_dict(self):
        categories, topics = expand_filter_identifiers({})
        self.assertEqual(categories, [])
        self.assertEqual(topics, [])

    def test_all_string(self):
        data = {"topic1": "all", "topic2": "all"}
        categories, topics = expand_filter_identifiers(data)
        self.assertEqual(categories, ["topic1", "topic2"])
        self.assertEqual(topics, [])

    def test_list_values_characters(self):
        data = {"topic1": ["a", "b"], "topic2": ["x"]}
        categories, topics = expand_filter_identifiers(data)
        self.assertEqual(categories, [])
        self.assertEqual(topics, ["topic1 a", "topic1 b", "topic2 x"])

    def test_list_values_numbers(self):
        data = {"topic1": [1, 2], "topic2": [3]}
        categories, topics = expand_filter_identifiers(data)
        self.assertEqual(categories, [])
        self.assertEqual(topics, ["topic1 1", "topic1 2", "topic2 3"])

    def test_mixed_values_characters(self):
        data = {"topic1": ["a"], "topic2": "all", "topic3": ["x", "y"]}
        categories, topics = expand_filter_identifiers(data)
        self.assertEqual(categories, ["topic2"])
        self.assertEqual(topics, ["topic1 a", "topic3 x", "topic3 y"])

    def test_mixed_values_numbers(self):
        data = {"topic1": [1], "topic2": "all", "topic3": [3, 4]}
        categories, topics = expand_filter_identifiers(data)
        self.assertEqual(categories, ["topic2"])
        self.assertEqual(topics, ["topic1 1", "topic3 3", "topic3 4"])



class TestMatchesFilter(unittest.TestCase):
    def test_group_filter_matches(self):
        # Category "min" is in article_identifiers
        self.assertTrue(matches_filter(['min'], [], ['min 1', 'reg 3', 'other 3']))

    def test_expanded_filter_matches(self):
        # Individual topic "min 2" matches article_identifiers
        self.assertTrue(matches_filter(['reg'], ['min 1', 'min 2'], ['min 2', 'other 523']))

    def test_no_match(self):
        # No matches
        self.assertFalse(matches_filter(['min'], ['reg 1', 'reg 2'], ['other 33', 'misc 446']))

    def test_empty_group_filter(self):
        # Empty group filter, but expanded filter matches
        self.assertTrue(matches_filter([], ['min 1'], ['min 1', 'other 23']))

    def test_empty_group_filter_no_individual_match(self):
        # Empty group filter, but expanded filter matches, but no match
        self.assertFalse(matches_filter([], ['min 1'], ['min 5', 'other 23']))

    def test_empty_expanded_filter(self):
        # Empty expanded filter, but group filter matches
        self.assertTrue(matches_filter(['reg'], [], ['reg 44', 'other 345']))

    def test_empty_expanded_filter_no_category_match(self):
        # Empty expanded filter, but group filter should not matches
        self.assertFalse(matches_filter(['reg'], [], ['port 44', 'other 345']))

    def test_empty_filters(self):
        # No filters selected
        self.assertFalse(matches_filter([], [], ["reg 1", "reg 2"]))

    def test_all_empty(self):
        # Everything empty
        self.assertFalse(matches_filter([], [], []))

