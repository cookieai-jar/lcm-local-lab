#!/usr/bin/env python3
"""Render ldap/tree.yaml + $LDAP_BASE_DN/$LDAP_DOMAIN into ldap/.generated/bootstrap.ldif.

Run via `make render` (the `renderer` docker-compose service), never by hand against
a live openldap container: osixia only applies bootstrap LDIF/schema on first start
against an empty database, so a tree.yaml change needs `make reset` to take effect.

Deliberately never emits a cn=admin entry: osixia/openldap creates that one itself
from LDAP_ADMIN_PASSWORD, and a duplicate aborts the whole bootstrap import.
"""

import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TREE_CONFIG = Path(os.environ.get('LDAP_TREE_CONFIG', REPO_ROOT / 'ldap' / 'tree.yaml'))
OUTPUT_PATH = REPO_ROOT / 'ldap' / '.generated' / 'bootstrap.ldif'


def require_env(name):
    value = os.environ.get(name, '').strip()
    if not value:
        sys.exit(f'{name} is not set (check .env) — refusing to render bootstrap.ldif')
    return value


def render_ou(name, base_dn):
    return (
        f'# organisational unit for {name}\n'
        f'dn: ou={name},{base_dn}\n'
        f'changetype: add\n'
        f'objectClass: organizationalUnit\n'
        f'ou: {name}\n'
    )


def render_group(group, base_dn, valid_ous):
    cn = group['cn']
    ou = group.get('ou', 'Groups')
    if ou not in valid_ous:
        sys.exit(
            f'group {cn!r} references ou {ou!r}, which is not listed in '
            f'organizational_units in {TREE_CONFIG}'
        )
    dn = f'cn={cn},ou={ou},{base_dn}'
    description = group.get('description')

    lines = [
        f'# group: {cn}\n',
        f'dn: {dn}\n',
        'changetype: add\n',
        'objectClass: groupOfUniqueNames\n',
        f'cn: {cn}\n',
    ]
    if description:
        lines.append(f'description: {description}\n')
    # groupOfUniqueNames MUST have >=1 uniqueMember; self-reference as a
    # placeholder until LCM/Access Profiles add real members.
    lines.append(f'uniqueMember: {dn}\n')
    return ''.join(lines)


def render_user(user, base_dn, domain, valid_ous):
    uid = user['uid']
    ou = user['ou']
    if ou not in valid_ous:
        sys.exit(
            f'user {uid!r} references ou {ou!r}, which is not listed in '
            f'organizational_units in {TREE_CONFIG}'
        )
    mail = user.get('mail') or f'{uid}@{domain}'
    is_active = 'TRUE' if user.get('is_active', True) else 'FALSE'

    return (
        f'# user: {user["cn"]} for unit {ou}\n'
        f'dn: uid={uid},ou={ou},{base_dn}\n'
        f'changetype: add\n'
        f'objectClass: inetOrgPerson\n'
        f'objectClass: accountStatus\n'
        f'cn: {user["cn"]}\n'
        f'sn: {user["sn"]}\n'
        f'uid: {uid}\n'
        f'mail: {mail}\n'
        f'userPassword: {user["password"]}\n'
        f'is-active: {is_active}\n'
    )


def main():
    base_dn = require_env('LDAP_BASE_DN')
    domain = require_env('LDAP_DOMAIN')

    if not TREE_CONFIG.exists():
        sys.exit(f'LDAP tree config not found: {TREE_CONFIG}')
    tree = yaml.safe_load(TREE_CONFIG.read_text()) or {}

    ous = tree.get('organizational_units') or []
    users = tree.get('users') or []
    groups = tree.get('groups') or []
    valid_ous = set(ous)

    entries = [render_ou(name, base_dn) for name in ous]
    entries += [render_user(user, base_dn, domain, valid_ous) for user in users]
    entries += [render_group(group, base_dn, valid_ous) for group in groups]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text('\n'.join(entries) + '\n')
    print(
        f'wrote {OUTPUT_PATH} ({len(ous)} OUs, {len(users)} users, '
        f'{len(groups)} groups, base DN {base_dn})'
    )


if __name__ == '__main__':
    main()
