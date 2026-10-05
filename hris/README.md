# LCM-Test-HRIS

A dummy HRIS source, built with OAA Runner, for testing Veza Lifecycle Management
birthright (joiner/mover/leaver) policies. All data is fictional and comes from
`fixtures/<scenario>.json` through the OAA Runner mock framework. There is no real
HRIS behind it.

Setup (installing dependencies, filling in `.env`, bringing up the stack) is covered
by the root [README.md](../README.md) — this file only covers what's specific to the
HRIS piece once the lab is up.

## Layout

```
config.yaml                     HRIS provider, Employee + Group sources (all mapping in YAML)
modules/lcm_test_hris.py        fetch(): BaseURLSession + maybe_mock_it + lazy_dict_table
modules/lcm_test_hris_mocks.py  @mock_response for /employees and /groups; picks fixture by LCM_SCENARIO
modules/lcm_test_hris_hooks.py  PRE_RUN guard: refuses any run unless VEZA_URL host is allowlisted
fixtures/{baseline,joiner,mover,leaver}.json
requirements.txt                extra Python deps for this connector; installed inside the hris
                                 container automatically (see root docker-compose.yml / Dockerfile)
```

This runs as the `hris` service in the root `docker-compose.yml`, built from the
`oaa-runner-internal` submodule's own `Dockerfile`+`runit.sh` — there's no local
Python/`uv` setup for this piece; `make hris-validate` / `make hris-run` (from the repo
root) drive it.

## Personas

| ID | Persona | Baseline | Change |
|---|---|---|---|
| E1001 | Root manager, very long hyphenated name | active FTE, Leadership | — |
| E1002 | Siobhán O'Connor: FTE (apostrophe, accent) | active, Engineering / Software Engineer | — |
| E1003 | José Núñez: FTE (accents) | active, Finance / Financial Analyst | — |
| E1004 | Priya Raman: contractor | active, `employment_types: [CONTRACTOR]` | — |
| E1005 | Anne-Marie Dubois-Laurent: mover (hyphens) | active, Sales / Account Executive | `mover` → Engineering / Solutions Engineer |
| E1006 | Kenji Watanabe: leaver | active, Support | `leaver` → terminated, termination_date 2026-10-01 |
| E1007 | Olu Adeyemi: already terminated | terminated | — |
| E1008 | Zoë Åkesson: pre-hire joiner | `pre-hire`, `is_active: false`, start 2026-10-05 | `joiner` → active |
| E1009 | Mateus Ferreira: new hire | (absent) | `joiner` → added, active |

Every employee has `is_test_account = true`, an `@example.com` email, membership in the
`LCM-Test` group, and a `LCM-Test <Function>` department. Managers point only at fake employees.

Scenarios are cumulative: baseline → joiner → mover → leaver, each the previous dataset plus one
change. Run them in that order.

Attributes a birthright rule can use: `department`, `job_title`, `work_location`,
`employment_types` (FULL_TIME / CONTRACTOR), `managers`, `start_date` (hire date),
`employment_status`, and `is_active` (true only when `employment_status == active`).
Custom properties: `hire_date`, `employment_type` (FTE / Contractor), `is_test_account`, `persona`.

## Run sequence (per scenario, from the repo root)

```bash
# 1. Validate (also tests connectivity to VEZA_URL)
make hris-validate

# 2. Local build, no Veza contact; writes hris/lcm-test-hris-<timestamp>.json
make hris-run SCENARIO=baseline        # then joiner, mover, leaver

# 3. Inspect the payload
f=$(ls -t hris/lcm-test-hris-*.json | head -1)
jq '.employees | length' "$f"
jq -r '.employees[] | "\(.id)\t\(.employment_status)\tactive=\(.is_active)\t\(.department.id)\t\(.job_title)"' "$f"
jq '[.employees[] | select(.custom_properties.is_test_account != true)] | length' "$f"   # expect 0
jq '.employees[] | select(.id == "E1008")' "$f"   # joiner;  E1005 for mover, E1006 for leaver

# 4. Push to the sandbox (only after review)
make hris-run SCENARIO=baseline PUSH=true    # then joiner, mover, leaver
```

Expected results:

| Scenario | Employees | active / pre-hire / terminated |
|---|---|---|
| baseline | 8 | 6 / 1 / 1 |
| joiner | 9 | 8 / 0 / 1 |
| mover | 9 | 8 / 0 / 1 |
| leaver | 9 | 7 / 0 / 2 |

Notes:
- `--dry_run=True` is not offline: it still looks up the provider in Veza and creates it if it
  doesn't exist. `make hris-run` without `PUSH=true` uses `--no_push=True` instead for local checks.
- Expect identity-mapping warnings on push. The fake emails won't match any IdP identity.
  They are not failures.
- `oaa validate_payload` targets CUSTOM_APP payloads and misreports HRIS ones (0 LocalUsers).
  Use the jq checks above instead.

## LCM provisioning source

`app.options.provisioning: true` is sent in the provider-create call, which makes the provider
selectable as an LCM source (Lifecycle Management → Policies → Create Policy → Configure Source).
It applies **only when the provider is first created**. If `LCM-Test-HRIS` already exists
without it, the provider has to be deleted and re-created.
