.PHONY: build check test update
build:
	python3 tools/build.py
check:
	python3 tools/validate.py
test: check
	python3 -m unittest discover -s tests -v
	node --test tests/*.test.cjs
update:
	python3 tools/upstream.py
	python3 tools/build.py
	$(MAKE) test
