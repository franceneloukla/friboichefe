.PHONY: scrape seed serve dev reset
VENV := .venv/bin/python

scrape:
	$(VENV) scraper/scrape_catalog.py

seed:
	$(VENV) server/seed.py

serve:
	bash server/run.sh

reset:
	rm -f data/store.db
	$(MAKE) seed
