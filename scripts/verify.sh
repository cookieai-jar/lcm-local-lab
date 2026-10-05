#!/bin/sh
# End-to-end smoke check for the lab stack. Run via `make verify`.
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

set -a
# shellcheck disable=SC1091
. ./.env
set +a

echo "=== docker compose ps ==="
docker compose ps

echo ""
echo "=== ldapsearch: every tree.yaml user, should all show is-active: TRUE ==="
docker exec openldap ldapsearch -x -LLL \
    -H ldap://localhost \
    -D "cn=admin,${LDAP_BASE_DN}" \
    -w "${LDAP_ADMIN_PASSWORD}" \
    -b "${LDAP_BASE_DN}" \
    "(objectClass=inetOrgPerson)" uid is-active

echo ""
echo "=== phpLDAPadmin HTTP check ==="
curl -s -o /dev/null -w 'http://localhost:8081/ -> HTTP %{http_code}\n' http://localhost:8081/

echo ""
echo "=== insight_point: recent logs (look for a registered edp_id, no auth errors) ==="
docker logs insight_point --tail 40
echo ""
echo "--- non-info log lines (errors/warnings) ---"
docker logs insight_point 2>&1 | grep -v '"level":"info"' || echo "(none)"
