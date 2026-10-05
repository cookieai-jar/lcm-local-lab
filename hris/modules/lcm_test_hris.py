"""Fetch module for the LCM-Test-HRIS dummy integration.

There is no real HRIS behind this integration: run it with MOCK_RESULTS=true so
maybe_mock_it() routes every GET to the handlers in lcm_test_hris_mocks.py.
"""

import logging
import time

from oaa.hooks.mock_responses import maybe_mock_it
from oaa.modules.base_url_session import BaseURLSession
from oaa.modules.lazy_dicts import lazy_dict_table
from oaa.modules.params_or_env import params_or_env

logger = logging.getLogger(__name__)

MAX_RETRIES = 5


class LcmTestHrisAPI:
    """Minimal REST client for the (fictional) LCM test HRIS."""

    def __init__(self, connection, source):
        self.base_url = params_or_env(connection, source, 'LCM_TEST_HRIS_BASE_URL')
        self._session = None

    @property
    def session(self):
        """Lazily build a BaseURLSession rooted at the HRIS base URL."""
        if not self._session:
            self._session = BaseURLSession(self.base_url)
        return self._session

    def get(self, path, params=None, _attempt=0, **kwargs):
        """GET a path, backing off exponentially on HTTP 429."""
        res = self.session.get(path, params=params, timeout=30)

        if res.status_code == 429 and _attempt < MAX_RETRIES:
            delay = 2 ** _attempt
            logger.warning('rate limited on %s, retrying in %ss', path, delay)
            time.sleep(delay)
            return self.get(path, params=params, _attempt=_attempt + 1, **kwargs)

        return res

    def fetch_paginated(self, path, resource_key='data', _next=None):
        """Yield records from `resource_key`, following `links.next` recursively."""
        res = self.get(_next or path)

        # Explicit status check: MockResponse.raise_for_status() raises a plain
        # Exception rather than requests.HTTPError.
        if res.status_code >= 400:
            raise RuntimeError(f'HRIS API error {res.status_code} for {path}')

        body = res.json()
        yield from body.get(resource_key, [])

        next_link = (body.get('links') or {}).get('next')
        if next_link:
            logger.info('fetching next page %s', next_link)
            yield from self.fetch_paginated(path, resource_key=resource_key, _next=next_link)


def _mapped_source_fields(source):
    """Return the raw field names referenced by the source's field_mapping."""
    return {
        (mapping.source_field or name)
        for name, mapping in (source.field_mapping or {}).items()
    }


def _backfill(records, fields):
    """Yield each record with every mapped field present (missing -> None)."""
    for record in records:
        for field in fields:
            record.setdefault(field, None)
        yield record


def fetch(connection=None, source=None, **kwargs):
    """Fetch employees or groups (per source.params.resource) as a lazy PETL table."""
    api = LcmTestHrisAPI(connection, source)
    maybe_mock_it(api, 'get', connection, source)

    records = api.fetch_paginated(
        source.params.get('resource', ''),
        resource_key=source.params.get('resource_key', 'data'),
    )
    return lazy_dict_table(_backfill(records, _mapped_source_fields(source)))
