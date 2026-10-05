"""Mock HRIS endpoints serving per-scenario fixtures from ../fixtures/<scenario>.json.

Loaded only via `logic_modules` in config.yaml; never imported by lcm_test_hris.py.
The scenario is chosen with the LCM_SCENARIO env var (baseline, joiner, mover, leaver,
rehire, convert).
Mock handlers receive no connection object, so the scenario is read from os.environ,
which oaa-runner populates from .env via required_env before fetch() runs.
"""

import json
import logging
import os
from pathlib import Path

from oaa.hooks.mock_responses import mock_response

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / 'fixtures'
SCENARIOS = ('baseline', 'joiner', 'mover', 'leaver', 'rehire', 'convert')


def load_scenario(name=None):
    """Load the fixture dataset for `name` (default: $LCM_SCENARIO)."""
    name = (name or os.environ.get('LCM_SCENARIO', '')).strip().lower()
    if name not in SCENARIOS:
        raise ValueError(f'LCM_SCENARIO must be one of {SCENARIOS}, got {name!r}')

    with open(FIXTURES_DIR / f'{name}.json', encoding='utf-8') as fh:
        data = json.load(fh)
    logger.info('serving mock scenario %s (%s employees)', name, len(data['employees']))
    return data


@mock_response(path='/employees')
def employees():
    """Employees for the active scenario (single page, no next link)."""
    return {'data': load_scenario()['employees']}


@mock_response(path='/groups')
def groups():
    """Department/team groups for the active scenario (single page, no next link)."""
    return {'data': load_scenario()['groups']}
