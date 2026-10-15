#!/usr/bin/env python3
"""Bounded OpenAlex discovery for ABC research. Standard library only; JSON stdout."""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import gzip
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://api.openalex.org'
CONTENT = 'https://content.openalex.org'
ENTITIES = {'works': 'W', 'authors': 'A', 'topics': 'T', 'sources': 'S',
            'institutions': 'I', 'publishers': 'P', 'funders': 'F'}
JSON_LIMIT = 10 * 1024 * 1024
CONTENT_LIMIT = 40 * 1024 * 1024


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class Failure(Exception):
    def __init__(self, kind, status=None):
        self.kind, self.status = kind, status
        super().__init__(kind)


def doi_key(value):
    return re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '',
                  str(value or '').strip(), flags=re.I).lower()


def identifier(entity, value):
    short = value.removeprefix('https://openalex.org/').rstrip('/')
    if re.fullmatch(ENTITIES[entity] + r'\d+', short, flags=re.I):
        return short.upper()
    doi = doi_key(value)
    if entity == 'works' and re.fullmatch(r'10\.\d{4,9}/\S+', doi):
        return 'https://doi.org/' + doi
    raise ValueError('Use a matching OpenAlex ID, or a DOI for works.')


def abstract_text(index):
    if not isinstance(index, dict):
        return None
    positions = {p: word for word, offsets in index.items() if isinstance(offsets, list)
                 for p in offsets if isinstance(p, int) and not isinstance(p, bool) and p >= 0}
    return ' '.join(str(positions[p]) for p in sorted(positions)) or None


def merge_records(records):
    """Merge exact DOI/ID duplicates, including records bridging two prior matches."""
    output, identities = [], {}
    for record in records:
        keys = ([('doi', doi_key(record['doi']))] if record.get('doi') else [])
        if record.get('id'):
            keys.append(('id', record['id']))
        matches = {identities[k] for k in keys if k in identities}
        if matches:
            slot = min(matches)
            target = output[slot]
            for other in sorted(matches - {slot}):
                for field, value in output[other].items():
                    if target.get(field) is None:
                        target[field] = value
                target['retrieved_ids'] = list(dict.fromkeys(
                    target.get('retrieved_ids', []) + output[other].get('retrieved_ids', [])))
                output[other] = None
                for key, old_slot in list(identities.items()):
                    if old_slot == other:
                        identities[key] = slot
            for field, value in record.items():
                if target.get(field) is None:
                    target[field] = value
        else:
            slot, target = len(output), dict(record)
            output.append(target)
        target['retrieved_ids'] = list(dict.fromkeys(
            target.get('retrieved_ids', []) + ([record['id']] if record.get('id') else [])))
        for key in keys:
            identities[key] = slot
    for record in output:
        if record is not None and 'abstract_inverted_index' in record:
            record['abstract_text'] = abstract_text(record['abstract_inverted_index'])
    return [r for r in output if r is not None]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Avoid forwarding authentication to publisher or arbitrary redirect hosts.
        raise Failure('redirect_refused', code)


class Client:
    def __init__(self, *, max_requests=12, retries=2, timeout=20, cache_dir=None,
                 cache_ttl=86400, refresh=False):
        self.key = os.environ.get('OPENALEX_API_KEY', '')
        self.max_requests, self.calls = max_requests, 0
        self.retries, self.timeout = retries, timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_ttl, self.refresh = cache_ttl, refresh
        self.last_call = 0.0
        self.log, self.warnings = [], []
        self.opener = urllib.request.build_opener(NoRedirect())

    def clean(self, value):
        rendered = json.dumps(value, ensure_ascii=False)
        if self.key:
            for secret in (self.key, urllib.parse.quote(self.key, safe=''),
                           urllib.parse.quote_plus(self.key)):
                rendered = rendered.replace(secret, '[REDACTED]')
        return json.loads(rendered)

    def request(self, path, params=None, *, content=False):
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('Expected a relative API path.')
        url = (CONTENT if content else BASE) + path
        if params:
            url += '?' + urllib.parse.urlencode(params)
        cache_path = None
        if self.cache_dir and not content:
            cache_path = self.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + '.json')
            if not self.refresh:
                try:
                    cached = json.loads(cache_path.read_text())
                    age = (dt.datetime.now(dt.timezone.utc) -
                           dt.datetime.fromisoformat(cached['retrieved_at'])).total_seconds()
                    if 0 <= age <= self.cache_ttl and isinstance(cached['data'], dict):
                        self.log.append({'url': url, 'cache_hit': True,
                                         'retrieved_at': cached['retrieved_at']})
                        return cached['data']
                except (OSError, ValueError, KeyError, TypeError):
                    pass
        headers = {'Accept': '*/*' if content else 'application/json',
                   'User-Agent': 'abc-research-generator/1.0'}
        if self.key:
            headers['Authorization'] = 'Bearer ' + self.key
        for attempt in range(self.retries + 1):
            if self.calls >= self.max_requests:
                raise Failure('request_limit')
            # Conservative pacing within this run; callers must also pace separate runs.
            time.sleep(max(0.0, 1.05 - (time.monotonic() - self.last_call)))
            self.calls += 1
            self.last_call = time.monotonic()
            entry = {'url': url, 'retrieved_at': stamp(), 'cache_hit': False}
            self.log.append(entry)
            try:
                req = urllib.request.Request(url, headers=headers)
                with self.opener.open(req, timeout=self.timeout) as response:
                    limit = CONTENT_LIMIT if content else JSON_LIMIT
                    raw = response.read(limit + 1)
                    if len(raw) > limit:
                        raise Failure('response_too_large')
                    entry['status'] = response.status
                    entry['usage'] = {k: v for k, v in response.headers.items()
                                      if k.lower().startswith('x-ratelimit')}
                if content:
                    return raw
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise Failure('invalid_response')
                if data.get('error'):
                    raise Failure('api_error')
                if cache_path:
                    try:
                        self.cache_dir.mkdir(parents=True, exist_ok=True)
                        temporary = cache_path.with_suffix('.' + str(os.getpid()) + '.tmp')
                        temporary.write_text(json.dumps(self.clean(
                            {'retrieved_at': entry['retrieved_at'], 'data': data})))
                        temporary.replace(cache_path)
                    except OSError:
                        self.warnings.append('cache_write_failed')
                return data
            except urllib.error.HTTPError as exc:
                entry['status'] = exc.code
                kind = ('authentication' if exc.code in (401, 403) else
                        'quota_or_rate_limit' if exc.code == 429 else
                        'not_found' if exc.code == 404 else
                        'server_error' if exc.code >= 500 else 'invalid_request')
                if exc.code == 400:
                    try:
                        detail = json.loads(exc.read(JSON_LIMIT))
                        if isinstance(detail, dict) and 'validation' in detail:
                            entry['validation'] = self.clean(detail['validation'])
                    except (ValueError, OSError, http.client.HTTPException):
                        pass
                if (exc.code != 429 and exc.code < 500) or attempt == self.retries:
                    raise Failure(kind, exc.code) from None
                delay = min(2 ** attempt, 8)
                retry_after = exc.headers.get('Retry-After') if exc.headers else None
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        try:
                            delay = max(delay, (email.utils.parsedate_to_datetime(retry_after) -
                                               dt.datetime.now(dt.timezone.utc)).total_seconds())
                        except (ValueError, TypeError):
                            pass
                if delay > 8:
                    raise Failure(kind, exc.code) from None
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
                if attempt == self.retries:
                    kind = ('incomplete_response' if isinstance(exc, http.client.IncompleteRead)
                            else 'network_or_tls')
                    raise Failure(kind) from None
                time.sleep(min(2 ** attempt, 8))
            except (ValueError, UnicodeError):
                raise Failure('invalid_json') from None


def report():
    return {'source': 'OpenAlex', 'run_at': stamp(), 'records': [], 'groups': [],
            'pages': [], 'api_total': None, 'truncated': False, 'failures': []}


def fail(result, exc):
    result['failures'].append({'kind': exc.kind, 'http_status': exc.status})
    result['truncated'] = True


def lookup(client, entity, value):
    data = client.request('/' + entity + '/' + urllib.parse.quote(identifier(entity, value), safe=''))
    if not data.get('id'):
        raise Failure('invalid_response')
    return data


def retrieve(client, path, params, *, per_page=25, max_pages=1, semantic=False, grouped=None):
    result = report()
    params = dict(params, per_page=per_page)
    if not semantic:
        params['cursor'] = '*'
    seen = set()
    for page in range(1, max_pages + 1):
        try:
            data = client.request(path, params)
            meta = data.get('meta') or {}
            if not isinstance(meta, dict):
                raise Failure('invalid_response')
            # Live list envelopes may include an empty group_by beside real results.
            is_grouped = (grouped if grouped is not None else
                          bool(params.get('group_by')) or bool(data.get('group_by')) or
                          ('results' not in data and 'group_by' in data))
            rows = data.get('group_by' if is_grouped else 'results')
            if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
                raise Failure('invalid_response')
            result['groups' if is_grouped else 'records'].extend(rows)
            result['pages'].append({'page': page, 'meta': meta})
            result['api_total'] = meta.get('count')
            cursor = meta.get('next_cursor')
            if semantic:
                result['coverage'] = 'semantic_ranked_candidates; not an exhaustive corpus'
                result['truncated'] = len(rows) >= per_page
                break
            if not cursor:
                total = result['api_total']
                result['truncated'] = (len(rows) >= per_page if is_grouped else
                                       isinstance(total, int) and total > len(result['records']))
                if is_grouped:
                    result['coverage'] = 'returned_groups_only; meta.count counts entities, not groups'
                break
            if page == max_pages:
                result['truncated'] = True
                result['stop_reason'] = 'page_limit'
                break
            if not client.key:
                result['truncated'] = True
                result['stop_reason'] = 'cursor_paging_requires_key'
                break
            if cursor in seen or cursor == params.get('cursor'):
                raise Failure('repeated_cursor')
            seen.add(cursor)
            params['cursor'] = cursor
        except Failure as exc:
            fail(result, exc)
            break
    result['records'] = merge_records(result['records'])
    result['record_count'] = len(result['records'])
    return result


def neighbourhood(client, value, *, limit=25):
    result = report()
    seed = lookup(client, 'works', value)
    result['seed'] = seed
    result['edges'], records = [], [seed]
    seed_id = identifier('works', seed['id'])
    for relation, field in (('references', 'referenced_works'), ('related', 'related_works')):
        ids = list(dict.fromkeys(seed.get(field) or []))
        selected = ids[:limit]
        if len(ids) > limit:
            result['truncated'] = True
        if not selected:
            continue
        try:
            batch = client.request('/works', {'filter': 'openalex:' + '|'.join(
                identifier('works', item) for item in selected), 'per_page': len(selected)})
            rows = batch.get('results')
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise Failure('invalid_response')
            records.extend(rows)
            returned = {r.get('id') for r in rows}
            result['edges'].extend({'from': seed['id'], 'to': item, 'relation': relation}
                                   for item in selected)
            missing = [item for item in selected if item not in returned]
            if missing:
                result.setdefault('unresolved_ids', []).extend(missing)
                result['truncated'] = True
        except Failure as exc:
            fail(result, exc)
    citing = retrieve(client, '/works', {'filter': 'cites:' + seed_id,
                      'sort': 'publication_date:desc'}, per_page=limit)
    records.extend(citing['records'])
    result['edges'].extend({'from': r['id'], 'to': seed['id'], 'relation': 'cites'}
                           for r in citing['records'] if r.get('id'))
    result['citing_coverage'] = {k: citing[k] for k in ('api_total', 'truncated', 'pages')}
    result['truncated'] |= citing['truncated']
    result['failures'].extend(citing['failures'])
    result['records'] = merge_records(records)
    result['record_count'] = len(result['records'])
    result['coverage'] = 'one hop; references/related capped per relation; citing papers newest first'
    return result


def content_file(client, value, fmt, output):
    work = lookup(client, 'works', value)
    if not (work.get('has_content') or {}).get(fmt):
        raise Failure('content_unavailable')
    short = identifier('works', work['id'])
    extension = 'pdf' if fmt == 'pdf' else 'grobid-xml'
    raw = client.request('/works/' + short + '.' + extension, content=True)
    if raw.startswith(b'\x1f\x8b'):
        import io
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as zipped:
                raw = zipped.read(CONTENT_LIMIT + 1)
        except (OSError, EOFError):
            raise Failure('invalid_content') from None
    if len(raw) > CONTENT_LIMIT:
        raise Failure('response_too_large')
    if fmt == 'pdf' and not raw.startswith(b'%PDF-'):
        raise Failure('invalid_content')
    if fmt == 'grobid_xml':
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(raw)
            if not any(e.tag.split('}')[-1].lower() == 'tei' for e in root.iter()):
                raise Failure('invalid_content')
        except ET.ParseError:
            raise Failure('invalid_content') from None
    # Exclusive creation prevents accidentally replacing a researcher's existing file.
    try:
        with Path(output).open('xb') as target:
            target.write(raw)
    except FileExistsError:
        raise Failure('output_exists') from None
    except OSError:
        raise Failure('output_write_failed') from None
    result = report()
    result['records'] = [work]
    result['content'] = {'path': str(Path(output).resolve()), 'format': fmt,
                         'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    return result


def bound(low, high):
    def parse(value):
        n = int(value)
        if not low <= n <= high:
            raise argparse.ArgumentTypeError(f'must be between {low} and {high}')
        return n
    return parse


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest='mode', required=True)
    commands = {}
    for mode in ('get', 'list', 'neighbourhood', 'oql', 'content'):
        child = sub.add_parser(mode)
        commands[mode] = child
        child.add_argument('--max-requests', type=bound(1, 50), default=12)
        child.add_argument('--retries', type=bound(0, 3), default=2)
        child.add_argument('--timeout', type=bound(1, 60), default=20)
        child.add_argument('--cache-dir')
        child.add_argument('--cache-ttl', type=bound(0, 2592000), default=86400)
        child.add_argument('--refresh', action='store_true')
        if mode in ('get', 'list'):
            child.add_argument('entity', choices=ENTITIES)
        if mode in ('get', 'neighbourhood', 'content'):
            child.add_argument('identifier')
        if mode in ('list', 'oql'):
            child.add_argument('--per-page', type=bound(1, 100), default=25)
            child.add_argument('--max-pages', type=bound(1, 20), default=1)
            child.add_argument('--select')
            child.add_argument('--sort')
    child = commands['list']
    searches = child.add_mutually_exclusive_group()
    searches.add_argument('--search')
    searches.add_argument('--semantic')
    searches.add_argument('--exact')
    child.add_argument('--filter')
    child.add_argument('--group-by')
    commands['neighbourhood'].add_argument('--limit', type=bound(1, 100), default=25)
    commands['oql'].add_argument('query')
    commands['oql'].add_argument('--execute', action='store_true',
                                 help='Validate/translate first, then execute if valid.')
    commands['content'].add_argument('--format', choices=('pdf', 'grobid_xml'), default='pdf')
    commands['content'].add_argument('--output', required=True)
    return root


def main(argv=None):
    root = parser()
    secret = os.environ.get('OPENALEX_API_KEY', '')
    forbidden = re.compile(r'(?:^--api[-_]key(?:=|$)|\bapi_key\s*[:=]|authorization\s*[:=]|bearer\s+\S+)', re.I)
    supplied = list(sys.argv[1:] if argv is None else argv)
    # Check before argparse can echo an unknown credential-bearing argument.
    if any(forbidden.search(v) or (secret and secret in v) for v in supplied):
        root.error('Credential-bearing arguments are not allowed; use OPENALEX_API_KEY.')
    args = vars(root.parse_args(supplied))
    if any(isinstance(v, str) and (forbidden.search(v) or (secret and secret in v))
           for v in args.values()):
        root.error('Credential-bearing arguments are not allowed; use OPENALEX_API_KEY.')
    mode = args.pop('mode')
    client = Client(**{k: args.pop(k) for k in ('max_requests', 'retries', 'timeout',
                                               'cache_dir', 'cache_ttl', 'refresh')})
    result = report()
    try:
        if mode == 'get':
            result['records'] = merge_records([lookup(client, args['entity'], args['identifier'])])
        elif mode == 'list':
            semantic = args.get('semantic')
            if semantic:
                if args['entity'] != 'works' or len(semantic) > 2000 or args['max_pages'] != 1:
                    raise ValueError('Semantic search: works only, <=2000 characters, one page.')
                if args.get('group_by') or args.get('sort'):
                    raise ValueError('Use a conventional query for sorting/grouping; retain semantic ranking.')
                if re.search(r'(?:^|[,|!])\s*(?:cited_by_count|(?:last_known_institutions\.)?country_code)\s*:',
                             args.get('filter') or ''):
                    raise ValueError('Unsupported semantic-search filter; use a separate conventional query.')
            params = {k: v for k, v in {'search': args.get('search'),
                      'search.semantic': semantic, 'search.exact': args.get('exact'),
                      'filter': args.get('filter'), 'sort': args.get('sort'),
                      'select': args.get('select'), 'group_by': args.get('group_by')}.items() if v}
            result = retrieve(client, '/' + args['entity'], params,
                              per_page=min(args['per_page'], 50) if semantic else args['per_page'],
                              max_pages=args['max_pages'], semantic=bool(semantic))
        elif mode == 'neighbourhood':
            result = neighbourhood(client, args['identifier'], limit=args['limit'])
        elif mode == 'oql':
            checked = client.request('/query/oql/' + urllib.parse.quote(args['query'], safe=''))
            result['translation'] = checked
            if (checked.get('validation') or {}).get('valid') is not True:
                raise Failure('invalid_oql')
            if args['execute']:
                params = {'oql': args['query']}
                params.update({k: args[k] for k in ('select', 'sort') if args.get(k)})
                query_structure = checked.get('oqo')
                grouped = bool(query_structure.get('group_by')) if isinstance(query_structure, dict) else None
                result = retrieve(client, '/', params, per_page=args['per_page'],
                                  max_pages=args['max_pages'], grouped=grouped)
                result['translation'] = checked
        else:
            result = content_file(client, args['identifier'], args['format'], args['output'])
    except Failure as exc:
        fail(result, exc)
    except ValueError as exc:
        result['failures'].append({'kind': 'invalid_input', 'message': str(exc)})
        result['truncated'] = True
    result.update({'request': {'mode': mode, **args, 'api_key_present': bool(client.key)},
                   'record_count': len(result['records']), 'requests_made': client.calls,
                   'provenance': client.log, 'warnings': client.warnings})
    print(json.dumps(client.clean(result), ensure_ascii=False, indent=2))
    return 2 if result['failures'] else 0


if __name__ == '__main__':
    sys.exit(main())
