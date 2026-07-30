PYTHON = python3
PIP = pip3
MAP ?= maps/easy

.PHONY: install run debug clean lint

install:
	$(PIP) install flake8 mypy

run:
	$(PYTHON) main.py $(MAP)

debug:
	$(PYTHON) -m pdb main.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

lint:
	flake8 .
	mypy . \
		--warn-return-any \
		--warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs \
		--check-untyped-defs