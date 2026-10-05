.PHONY: help install render up down reset verify hris-validate hris-run clean

help: ## Show this help.
	@sed -ne 's/^\([^[:space:]]*\):.*##/\1:\t/p' $(MAKEFILE_LIST) | column -t -s $$'\t'

install: ## Install Homebrew/Colima/docker/docker-compose if missing, init submodules, start Colima.
	./scripts/install_deps.sh

render: ## Render ldap/tree.yaml -> ldap/.generated/bootstrap.ldif.
	docker compose run --rm renderer

up: render ## Render LDAP bootstrap data, then bring up openldap + phpldapadmin + insight_point.
	docker compose pull openldap phpldapadmin insightpoint
	docker compose up -d openldap phpldapadmin insightpoint

down: ## Stop the lab containers (keeps the LDAP database volume).
	docker compose down

reset: ## Wipe the LDAP database and bring the lab back up. Required after editing ldap/tree.yaml.
	docker compose down -v
	$(MAKE) up

verify: ## Smoke-check the running stack (compose ps, ldapsearch, phpLDAPadmin, insight_point logs).
	./scripts/verify.sh

hris-validate: ## Validate hris/config.yaml against Veza (also checks connectivity).
	docker compose run --rm hris app validate --config=config.yaml

# Usage: make hris-run SCENARIO=baseline              (local build only, no push)
#        make hris-run SCENARIO=joiner PUSH=true      (pushes to VEZA_URL)
hris-run: ## Run an HRIS scenario. SCENARIO=baseline|joiner|mover|leaver|rehire|convert, PUSH=true to push.
	docker compose run --rm \
		-e LCM_SCENARIO=$(SCENARIO) \
		-e MOCK_RESULTS=true \
		hris app run --config_file=config.yaml $(if $(filter true,$(PUSH)),,--no_push=True) --save-json=True

clean: ## Stop containers, drop volumes, remove generated/output files.
	docker compose down -v
	rm -rf ldap/.generated
	rm -rf hris/__pycache__ hris/modules/__pycache__
	rm -f hris/lcm-test-hris-*.json
