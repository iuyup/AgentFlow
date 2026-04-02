.PHONY: sync serve build deploy

sync:
	python sync_docs.py

serve: sync
	mkdocs serve

build: sync
	mkdocs build

deploy: build
	mkdocs gh-deploy
