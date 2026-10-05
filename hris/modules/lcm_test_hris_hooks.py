"""Hooks for LCM-Test-HRIS.

Only one hook: a PRE_RUN guard that refuses to run against any Veza tenant whose
hostname is not on VEZA_URL_ALLOWLIST. It runs for every mode (including
--dry_run, which still contacts Veza to look up / create the provider).
"""

import logging
import os
from urllib.parse import urlparse

from oaa.hooks.decorators import hook, OAAHookEvent

logger = logging.getLogger(__name__)


def _hostname(url):
    """Return the lowercase hostname of a URL, tolerating a missing scheme."""
    url = str(url or '').strip()
    if url and '://' not in url:
        url = f'https://{url}'
    return (urlparse(url).hostname or '').lower()


@hook(event=OAAHookEvent.PRE_RUN)
def enforce_veza_url_allowlist(*args, config=None, **kwargs):
    """Abort the run unless VEZA_URL's hostname is in VEZA_URL_ALLOWLIST."""
    veza_url = (config and config.VEZA_URL) or os.getenv('VEZA_URL')
    allowlist = {
        _hostname(h) for h in os.getenv('VEZA_URL_ALLOWLIST', '').split(',') if h.strip()
    }
    host = _hostname(veza_url)

    if not allowlist:
        raise SystemExit('VEZA_URL_ALLOWLIST is empty; refusing to run')
    if host not in allowlist:
        raise SystemExit(f'Veza host {host or "<unset>"!r} is not on VEZA_URL_ALLOWLIST')

    logger.info('Veza host %s is allowlisted', host)
