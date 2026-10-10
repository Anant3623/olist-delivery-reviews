PYTHON ?= python3
PSQL ?= psql
PGDATABASE ?= olist_delivery_analysis

export PSQL PGDATABASE

.PHONY: help all load staging quality mart analysis robustness export stats geography summarize validate

help:
	@echo 'make all       Rebuild the SQL pipeline and analysis in PGDATABASE'
	@echo 'make summarize Recreate readable result CSVs from included clean exports'
	@echo 'make validate  Check order grain, dates, nulls, seller attribution and totals'

# Keep the dependent stages ordered, including when make -j is requested.
all:
	$(MAKE) load
	$(MAKE) staging
	$(MAKE) quality
	$(MAKE) mart
	$(MAKE) analysis
	$(MAKE) robustness
	$(MAKE) export
	$(MAKE) stats
	$(MAKE) geography
	$(MAKE) summarize
	$(MAKE) validate

load:
	$(PYTHON) python/load_raw.py

staging:
	$(PSQL) -X -v ON_ERROR_STOP=1 -f sql/02_staging.sql

quality:
	$(PSQL) -X -v ON_ERROR_STOP=1 -f sql/03_dq_checks.sql -o analysis/data_quality_checks.txt

mart:
	$(PSQL) -X -v ON_ERROR_STOP=1 -f sql/05_mart.sql

analysis:
	$(PSQL) -X -v ON_ERROR_STOP=1 -f sql/04_analysis.sql -o analysis/business_analysis.txt

robustness:
	$(PSQL) -X -v ON_ERROR_STOP=1 -f sql/06_robustness.sql -o analysis/within_group_analysis.txt

export:
	$(PYTHON) python/export_data.py

stats:
	$(PYTHON) python/stats_test.py > analysis/mann_whitney_test.txt

geography:
	$(PYTHON) python/geographic_check.py > analysis/geographic_check.txt

summarize:
	$(PYTHON) python/summarize_analysis.py

validate:
	$(PYTHON) python/validate_outputs.py
