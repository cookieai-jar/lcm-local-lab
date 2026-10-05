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
fixtures/{baseline,joiner,mover,leaver,rehire,convert}.json
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
| E1003 | José Núñez: FTE (accents), later FTE → contractor | active, Finance / Financial Analyst | `convert` → `employment_types: [CONTRACTOR]`, job_title "Financial Analyst (Contract)" |
| E1004 | Priya Raman: contractor, later contractor → FTE | active, `employment_types: [CONTRACTOR]` | `convert` → `employment_types: [FULL_TIME]`, job_title "QA Engineer" |
| E1005 | Anne-Marie Dubois-Laurent: mover (hyphens) | active, Sales / Account Executive | `mover` → Engineering / Solutions Engineer |
| E1006 | Kenji Watanabe: leaver | active, Support | `leaver` → terminated, termination_date 2026-10-01 |
| E1007 | Olu Adeyemi: already terminated, later rehired | terminated | `rehire` → active, new hire_date |
| E1008 | Zoë Åkesson: pre-hire joiner | `pre-hire`, `is_active: false`, start 2026-10-05 | `joiner` → active |
| E1009 | Mateus Ferreira: new hire | (absent) | `joiner` → added, active |

Every employee has `is_test_account = true`, an `@example.com` email, membership in the
`LCM-Test` group, and a `LCM-Test <Function>` department. Managers point only at fake employees.

Scenarios are cumulative: baseline → joiner → mover → leaver → rehire → convert, each the
previous dataset plus one or two changes. Run them in that order.

Attributes a birthright rule can use: `department`, `job_title`, `work_location`,
`employment_types` (FULL_TIME / CONTRACTOR), `managers`, `start_date` (hire date),
`employment_status`, and `is_active` (true only when `employment_status == active`).
Custom properties: `hire_date`, `employment_type` (FTE / Contractor), `is_test_account`, `persona`.

## Run sequence (per scenario, from the repo root)

```bash
# 1. Validate (also tests connectivity to VEZA_URL)
make hris-validate

# 2. Local build, no Veza contact; writes hris/lcm-test-hris-<timestamp>.json
make hris-run SCENARIO=baseline        # then joiner, mover, leaver, rehire, convert

# 3. Inspect the payload
f=$(ls -t hris/lcm-test-hris-*.json | head -1)
jq '.employees | length' "$f"
jq -r '.employees[] | "\(.id)\t\(.employment_status)\tactive=\(.is_active)\t\(.department.id)\t\(.job_title)"' "$f"
jq '[.employees[] | select(.custom_properties.is_test_account != true)] | length' "$f"   # expect 0
jq '.employees[] | select(.id == "E1008")' "$f"   # joiner;  E1005 for mover, E1006 for leaver, E1007 for rehire, E1003/E1004 for convert

# 4. Push to the sandbox (only after review)
make hris-run SCENARIO=baseline PUSH=true    # then joiner, mover, leaver, rehire, convert
```

Expected results:

| Scenario | Employees | active / pre-hire / terminated |
|---|---|---|
| baseline | 8 | 6 / 1 / 1 |
| joiner | 9 | 8 / 0 / 1 |
| mover | 9 | 8 / 0 / 1 |
| leaver | 9 | 7 / 0 / 2 |
| rehire | 9 | 8 / 0 / 1 |
| convert | 9 | 8 / 0 / 1 |

Notes:
- `--dry_run=True` is not offline: it still looks up the provider in Veza and creates it if it
  doesn't exist. `make hris-run` without `PUSH=true` uses `--no_push=True` instead for local checks.
- Expect identity-mapping warnings on push. The fake emails won't match any IdP identity.
  They are not failures.
- `oaa validate_payload` targets CUSTOM_APP payloads and misreports HRIS ones (0 LocalUsers).
  Use the jq checks above instead.

## Setting up the LCM policy

Everything below is one-time console setup, done after the lab is up (root README's Quickstart)
and after `LCM-Test-HRIS` exists as a Veza provider (see the note on that below).

### 1. `LCM-Test-HRIS` as an LCM source

`app.options.provisioning: true` is sent in the provider-create call, which makes the provider
selectable as an LCM source (Lifecycle Management → Policies → Create Policy → Configure Source).
It applies **only when the provider is first created** — this happens on the first **real** push
(`make hris-run SCENARIO=baseline PUSH=true`); a `--no_push` build-only run never creates the
provider. If `LCM-Test-HRIS` already exists without `provisioning: true` (e.g. it was created by
an earlier `--no_push` experiment against an older `oaa-runner` version, or manually), it has to be
deleted and re-created in the Veza console for this flag to apply.

### 2. Register `openldap` as an LDAP integration

In the Veza console, go to **Integrations → Add Integration**, search for "LDAP", and configure
it with this lab's specifics:

| Field | Value | Why |
|---|---|---|
| Insight Point | the one created in the root README's "One-time setup" | lets Veza reach `openldap`, which isn't publicly exposed |
| IDP Name | `LCM-Test-OpenLDAP` (or similar) | internal identifier only |
| LDAP URL | `ldap://openldap:389` | `openldap` is the container hostname on the `ldap_network` Docker network the Insight Point shares with it; `LDAP_TLS=false` in `docker-compose.yml`, so no `ldaps://`/CA cert for this lab |
| Users Base DN | `$LDAP_BASE_DN` (e.g. `dc=example,dc=org`) | covers every OU in `ldap/tree.yaml`, not just one |
| Groups Base DN | same as Users Base DN | `ldap/tree.yaml` doesn't define any LDAP groups yet |
| Bind DN or User | `cn=admin,$LDAP_BASE_DN` | osixia/openldap's auto-created admin account |
| Bind Password | `$LDAP_ADMIN_PASSWORD` | from `.env` |
| Users Object Class | `inetOrgPerson,accountStatus` | **both**, per the comment at the top of `ldap/custom.schema` — `accountStatus` is the AUXILIARY class carrying `is-active`; omitting it from this list means the connector's search filter won't match these users |
| Groups Object Class | leave default (`groupOfUniqueNames`) | unused until `ldap/tree.yaml` defines groups |

Click **Create Integration** and wait for the first extraction to succeed — required before this
integration can be used as an LCM target.

![LDAP integration Configure page filled in for this lab, including the is-active activation strategy from step 3 below](images/ldap-integration-setup.png)

### 3. Enable provisioning on it

1. Open the `LCM-Test-OpenLDAP` integration → **Edit**.
2. Check **Enable usage for Provisioning** → **Save Configuration**.
3. Set the activation-detection strategy to match `ldap/custom.schema`'s `is-active` attribute
   (Strategy A — `is-active` is a positive "active" flag, not an "inactive/locked" one):
   - `active_user_attribute`: `is-active`
   - `active_user_value_when_active`: `TRUE`
   - `active_user_value_when_inactive`: `FALSE`

   (matches the literal strings `scripts/render_ldap_bootstrap.py` writes — `is-active: TRUE` /
   `is-active: FALSE`.)

### 4. Create the policy

1. **LCM → Policies → Create Policy.**
2. Name it (e.g. `LCM-Test: HRIS birthright → OpenLDAP`), and select **`LCM-Test-HRIS`** as the
   **Primary Identity Source**.
3. In the draft policy, open **Workflows → Create workflow** and add a **Sync Identities** action
   mapping HRIS employee fields to LDAP attributes.

This lab uses **one fixed OU for every synced employee** regardless of department — the common
real-world pattern unless an org is geographically distributed (region/country OUs), which this
lab doesn't model. `ldap/tree.yaml` defines `Employees` for this; `IT`/`Marketing` are unrelated
seed data used to smoke-test the rendering pipeline, not an LCM target.

In the Sync Identities action's **Action Synced Attributes**, map at least:

| Destination attribute | Formatter (source → value) | Why |
|---|---|---|
| `id` (the DN) | `uid={employee_number},ou=Employees,dc=example,dc=org` | replace `dc=example,dc=org` with your actual `$LDAP_BASE_DN`; this is the only universally required attribute for LDAP user creation |
| `uid` | `{employee_number}` | LDAP convention expects the entry to also carry the attribute matching its own RDN (see how `scripts/render_ldap_bootstrap.py` writes the seed users) |
| `cn` | `{full_name}` | required by `inetOrgPerson` |
| `sn` | `{last_name}` | required by `inetOrgPerson` |
| `mail` | `{email}` | |

Set **Action Unique Identifier** to `id` (the DN) so re-runs match the same entry instead of
creating duplicates — HRIS's `unique_id`/`employee_number` isn't itself an LDAP identifier, so the
DN Formatter above is what ties a given employee to a given LDAP entry across runs.

Not yet verified empirically: whether a newly-created entry automatically gets the `accountStatus`
auxiliary class (needed for `is-active` to be settable) just from the integration's configured
Users Object Class, or whether `objectClass` needs its own explicit mapping here. Check this when
you actually dry-run the workflow — if deactivation fails on a newly-created user, this is the
first thing to check.

4. Dry-run the workflow against a representative HRIS identity, publish the version, then
   **LCM → Policies → (policy) → ⋮ → Enable**. Policies run on source extraction — a dry run does
   not test LDAP connectivity.
