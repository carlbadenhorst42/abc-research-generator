"""Offline behavioural tests. Run: python3 -m unittest discover -s scripts -v"""
import contextlib
import gzip
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

import openalex as oa


class FakeClient:
    def __init__(self, responses, key='fixture-key'):
        self.responses = iter(responses)
        self.key = key
        self.seen = []

    def request(self, path, params=None, **kwargs):
        self.seen.append((path, dict(params or {})))
        item = next(self.responses)
        if isinstance(item, Exception):
            raise item
        return item


def work(n=1, **kwargs):
    return {'id': f'https://openalex.org/W{n}', **kwargs}


class RetrievalTests(unittest.TestCase):
    def test_doi_resolution(self):
        client = FakeClient([work()])
        oa.lookup(client, 'works', 'https://doi.org/10.1234/ABC')
        self.assertEqual(client.seen[0][0], '/works/https%3A%2F%2Fdoi.org%2F10.1234%2Fabc')
        with self.assertRaises(ValueError):
            oa.identifier('authors', 'W1')

    def test_abstract_order_and_missing(self):
        self.assertEqual(oa.abstract_text({'learning': [1, 3], 'Design': [0], 'for': [2]}),
                         'Design learning for learning')
        self.assertIsNone(oa.abstract_text(None))
        self.assertIsNone(oa.abstract_text({'bad': [-1, '2', True]}))

    def test_duplicate_bridge_retains_complementary_metadata(self):
        rows = [work(1, display_name='A'), {'doi': '10.1234/x', 'publication_year': 2020},
                work(1, doi='https://doi.org/10.1234/X'), work(2, doi='10.1234/x')]
        merged = oa.merge_records(rows)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['publication_year'], 2020)
        self.assertIn('https://openalex.org/W2', merged[0]['retrieved_ids'])

    def test_cursor_paging(self):
        client = FakeClient([{'results': [work(1)], 'meta': {'count': 2, 'next_cursor': 'a'}},
                             {'results': [work(2)], 'meta': {'count': 2}}])
        result = oa.retrieve(client, '/works', {}, per_page=1, max_pages=2)
        self.assertEqual(result['record_count'], 2)
        self.assertFalse(result['truncated'])
        self.assertEqual(client.seen[1][1]['cursor'], 'a')

    def test_live_list_envelope_with_empty_groups(self):
        client = FakeClient([{'results': [work(1)], 'group_by': [], 'meta': {'count': 1}}])
        result = oa.retrieve(client, '/works', {})
        self.assertEqual(result['record_count'], 1)
        self.assertEqual(result['groups'], [])

    def test_keyless_cursor_stops_explicitly(self):
        client = FakeClient([{'results': [work()], 'meta': {'next_cursor': 'a'}}], key='')
        result = oa.retrieve(client, '/works', {}, max_pages=2)
        self.assertEqual(result['stop_reason'], 'cursor_paging_requires_key')
        self.assertEqual(len(client.seen), 1)

    def test_partial_results_survive_failure(self):
        client = FakeClient([{'results': [work()], 'meta': {'next_cursor': 'a'}},
                             oa.Failure('quota_or_rate_limit', 429)])
        result = oa.retrieve(client, '/works', {}, max_pages=2)
        self.assertEqual(result['record_count'], 1)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['failures'][0]['http_status'], 429)

    def test_repeated_cursor(self):
        client = FakeClient([{'results': [work()], 'meta': {'next_cursor': 'a'}},
                             {'results': [work(2)], 'meta': {'next_cursor': 'a'}}])
        result = oa.retrieve(client, '/works', {}, max_pages=3)
        self.assertEqual(result['failures'][0]['kind'], 'repeated_cursor')

    def test_group_paging_does_not_use_entity_total_as_group_total(self):
        client = FakeClient([{'group_by': [{'key': 'article', 'count': 1000}],
                             'meta': {'count': 1000, 'next_cursor': 'g'}},
                            {'group_by': [{'key': 'book', 'count': 100}], 'meta': {'count': 1100}}])
        result = oa.retrieve(client, '/works', {'group_by': 'type'}, per_page=2, max_pages=2)
        self.assertEqual(len(result['groups']), 2)
        self.assertFalse(result['truncated'])

    def test_semantic_ranking_has_no_cursor(self):
        client = FakeClient([{'results': [work()], 'meta': {'count': 999, 'next_cursor': 'x'}}])
        result = oa.retrieve(client, '/works', {'search.semantic': 'feedback'}, semantic=True)
        self.assertNotIn('cursor', client.seen[0][1])
        self.assertIn('not an exhaustive corpus', result['coverage'])

    def test_neighbourhood_edges_and_unresolved_ids(self):
        seed = work(1, referenced_works=['https://openalex.org/W2', 'https://openalex.org/W3'],
                    related_works=['https://openalex.org/W4'])
        client = FakeClient([seed, {'results': [work(2)]}, {'results': [work(4)]},
                             {'results': [work(5)], 'meta': {'count': 1}}])
        result = oa.neighbourhood(client, 'W1', limit=2)
        self.assertEqual(result['unresolved_ids'], ['https://openalex.org/W3'])
        self.assertIn({'from': 'https://openalex.org/W5', 'to': seed['id'], 'relation': 'cites'},
                      result['edges'])
        self.assertEqual(result['record_count'], 4)

    def test_content_unavailable_creates_no_file(self):
        client = FakeClient([work(has_content={'pdf': False})])
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'seed.pdf'
            with self.assertRaises(oa.Failure) as caught:
                oa.content_file(client, 'W1', 'pdf', target)
            self.assertEqual(caught.exception.kind, 'content_unavailable')
            self.assertFalse(target.exists())

    def test_content_validation_and_exclusive_output(self):
        seed = work(has_content={'pdf': True})
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'seed.pdf'
            result = oa.content_file(FakeClient([seed, b'%PDF-1.7\nfixture']), 'W1', 'pdf', target)
            self.assertEqual(result['content']['bytes'], target.stat().st_size)
            with self.assertRaises(oa.Failure) as caught:
                oa.content_file(FakeClient([seed, b'%PDF-new']), 'W1', 'pdf', target)
            self.assertEqual(caught.exception.kind, 'output_exists')
            self.assertEqual(target.read_bytes(), b'%PDF-1.7\nfixture')
            with self.assertRaises(oa.Failure):
                oa.content_file(FakeClient([seed, b'<html>error</html>']), 'W1', 'pdf', Path(temp) / 'bad')

    def test_gzip_xml_and_old_wrapper(self):
        raw = b'<html><body><tei><text><div>Findings</div></text></tei></body></html>'
        seed = work(has_content={'grobid_xml': True})
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'seed.xml'
            oa.content_file(FakeClient([seed, gzip.compress(raw)]), 'W1', 'grobid_xml', target)
            self.assertEqual(target.read_bytes(), raw)


class ClientTests(unittest.TestCase):
    def response(self, data):
        response = Mock()
        response.read.return_value = json.dumps(data).encode()
        response.status = 200
        response.headers = {'X-RateLimit-Remaining': '100'}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    @patch.dict(os.environ, {'OPENALEX_API_KEY': 'very-secret-ABC'})
    @patch.object(oa.time, 'sleep')
    def test_authentication_cache_and_redaction(self, sleep):
        with tempfile.TemporaryDirectory() as temp:
            client = oa.Client(cache_dir=temp)
            client.opener = Mock()
            client.opener.open.return_value = self.response(work(display_name='very-secret-ABC'))
            client.request('/works/W1')
            req = client.opener.open.call_args.args[0]
            self.assertEqual(req.get_header('Authorization'), 'Bearer very-secret-ABC')
            self.assertNotIn('very-secret-ABC', next(Path(temp).glob('*.json')).read_text())
            data = client.request('/works/W1')
            self.assertEqual(client.calls, 1)
            self.assertTrue(client.log[-1]['cache_hit'])
            self.assertEqual(data['display_name'], '[REDACTED]')

    @patch.object(oa.time, 'sleep')
    def test_long_retry_after_stops(self, sleep):
        client = oa.Client()
        client.opener = Mock()
        client.opener.open.side_effect = urllib.error.HTTPError(
            'https://api.openalex.org/works', 429, 'quota', {'Retry-After': '3600'}, None)
        with self.assertRaises(oa.Failure) as caught:
            client.request('/works')
        self.assertEqual(caught.exception.kind, 'quota_or_rate_limit')
        self.assertEqual(client.calls, 1)

    @patch.object(oa.time, 'sleep')
    def test_retries_count_against_request_budget(self, sleep):
        client = oa.Client(max_requests=1)
        client.opener = Mock()
        client.opener.open.side_effect = urllib.error.URLError('offline')
        with self.assertRaises(oa.Failure) as caught:
            client.request('/works')
        self.assertEqual(caught.exception.kind, 'request_limit')
        self.assertEqual(client.calls, 1)

    @patch.object(oa.time, 'sleep')
    def test_authentication_failure_not_retried(self, sleep):
        client = oa.Client()
        client.opener = Mock()
        client.opener.open.side_effect = urllib.error.HTTPError('url', 401, 'no', {}, None)
        with self.assertRaises(oa.Failure) as caught:
            client.request('/works')
        self.assertEqual(caught.exception.kind, 'authentication')
        self.assertEqual(client.calls, 1)

    def test_redirect_does_not_forward_key(self):
        with self.assertRaises(oa.Failure):
            oa.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.org')

    @patch.object(oa.time, 'sleep')
    def test_incomplete_response_retries_within_budget(self, sleep):
        client = oa.Client(retries=1, max_requests=2)
        broken = self.response({})
        broken.read.side_effect = http.client.IncompleteRead(b'{', 100)
        client.opener = Mock()
        client.opener.open.side_effect = [broken, self.response(work())]
        self.assertEqual(client.request('/works/W1')['id'], work()['id'])
        self.assertEqual(client.calls, 2)

    @patch.object(oa.time, 'sleep')
    @patch.dict(os.environ, {'OPENALEX_API_KEY': 'synthetic-test-key'})
    def test_incomplete_second_page_preserves_cli_json_and_prior_rows(self, sleep):
        first = self.response({'results': [work()], 'group_by': [],
                               'meta': {'count': 2, 'next_cursor': 'page-two'}})
        broken = self.response({})
        broken.read.side_effect = http.client.IncompleteRead(b'{', 100)
        opener = Mock()
        opener.open.side_effect = [first, broken]
        output = io.StringIO()
        with patch.object(oa.urllib.request, 'build_opener', return_value=opener), contextlib.redirect_stdout(output):
            status = oa.main(['list', 'works', '--max-pages', '2', '--retries', '0'])
        result = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(result['record_count'], 1)
        self.assertEqual(result['failures'][0]['kind'], 'incomplete_response')
        self.assertTrue(result['truncated'])
        self.assertEqual(result['requests_made'], 2)

    @patch.object(oa.time, 'sleep')
    def test_incomplete_reads_cannot_exceed_request_budget(self, sleep):
        client = oa.Client(retries=2, max_requests=1)
        client.opener = Mock()
        client.opener.open.side_effect = http.client.IncompleteRead(b'', 10)
        with self.assertRaises(oa.Failure) as caught:
            client.request('/works')
        self.assertEqual(caught.exception.kind, 'request_limit')
        self.assertEqual(client.calls, 1)

    @patch.object(oa.time, 'sleep')
    def test_incomplete_http_error_body_retains_structured_failure(self, sleep):
        body = Mock()
        body.read.side_effect = http.client.IncompleteRead(b'{', 10)
        client = oa.Client(retries=0)
        client.opener = Mock()
        client.opener.open.side_effect = urllib.error.HTTPError('url', 400, 'invalid', {}, body)
        with self.assertRaises(oa.Failure) as caught:
            client.request('/works')
        self.assertEqual(caught.exception.kind, 'invalid_request')
        self.assertEqual(caught.exception.status, 400)


class CommandTests(unittest.TestCase):
    def run_cli(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = oa.main(args)
        return status, json.loads(output.getvalue())

    @patch.object(oa.Client, 'request')
    def test_oql_validation_only(self, request):
        request.return_value = {'validation': {'valid': True}, 'oql': 'works where year is (2024)'}
        status, result = self.run_cli(['oql', 'works where year is (2024)'])
        self.assertEqual(status, 0)
        self.assertEqual(request.call_count, 1)
        self.assertIn('translation', result)

    @patch.object(oa.Client, 'request')
    def test_invalid_oql_never_executes(self, request):
        request.return_value = {'validation': {'valid': False, 'errors': ['unknown field']}}
        status, result = self.run_cli(['oql', 'works where nonsense is (1)', '--execute'])
        self.assertEqual(status, 2)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(result['failures'][0]['kind'], 'invalid_oql')

    @patch.object(oa.Client, 'request')
    def test_oql_execution_root(self, request):
        request.side_effect = [{'validation': {'valid': True}}, {'results': [work()], 'meta': {'count': 1}}]
        status, result = self.run_cli(['oql', 'works where year is (2024)', '--execute'])
        self.assertEqual(status, 0)
        self.assertEqual(request.call_args.args[0], '/')
        self.assertEqual(result['record_count'], 1)

    @patch.object(oa.Client, 'request')
    def test_oql_literal_group_by_preserves_paper_results(self, request):
        request.side_effect = [
            {'validation': {'valid': True}, 'oqo': {'get_rows': 'works', 'filter_rows': []}},
            {'results': [work()], 'group_by': [], 'meta': {'count': 1}}]
        status, result = self.run_cli(['oql', 'works where title has (group by)', '--execute'])
        self.assertEqual(status, 0)
        self.assertEqual(result['record_count'], 1)
        self.assertFalse(result['truncated'])

    @patch.object(oa.Client, 'request')
    def test_oql_grouping_uses_validated_structure(self, request):
        request.side_effect = [
            {'validation': {'valid': True}, 'oqo': {'get_rows': 'works', 'group_by': [{'column_id': 'type'}]}},
            {'results': [], 'group_by': [{'key': 'article', 'count': 5}], 'meta': {'count': 5}}]
        status, result = self.run_cli(['oql', 'works where year is (2024) group by type', '--execute'])
        self.assertEqual(status, 0)
        self.assertEqual(result['groups'][0]['count'], 5)
        self.assertEqual(result['record_count'], 0)

    @patch.object(oa.Client, 'request')
    def test_oql_empty_groups_are_recognised_from_structure(self, request):
        request.side_effect = [
            {'validation': {'valid': True}, 'oqo': {'get_rows': 'works', 'group_by': [{'column_id': 'type'}]}},
            {'group_by': [], 'meta': {'count': 0}}]
        status, result = self.run_cli(['oql', 'works where year is (2024) group by type', '--execute'])
        self.assertEqual(status, 0)
        self.assertEqual(result['groups'], [])
        self.assertFalse(result['truncated'])

    @patch.object(oa.Client, 'request')
    def test_semantic_limits_fail_before_network(self, request):
        for extra in (['--max-pages', '2'], ['--group-by', 'type'], ['--filter', 'cited_by_count:>10']):
            status, result = self.run_cli(['list', 'works', '--semantic', 'feedback', *extra])
            self.assertEqual(status, 2)
            self.assertEqual(result['failures'][0]['kind'], 'invalid_input')
        request.assert_not_called()

    @patch.object(oa.Client, 'request')
    def test_research_query_can_discuss_authorization(self, request):
        request.return_value = {'results': [], 'group_by': [], 'meta': {'count': 0}}
        status, result = self.run_cli(['list', 'works', '--search', 'student authorization and consent'])
        self.assertEqual(status, 0)

    @patch.dict(os.environ, {'OPENALEX_API_KEY': 'fixture-SECRET'})
    def test_unknown_argument_does_not_echo_credential(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
            oa.main(['get', 'works', 'W1', '--api_key', 'fixture-SECRET'])
        self.assertNotIn('fixture-SECRET', error.getvalue())


if __name__ == '__main__':
    unittest.main()
