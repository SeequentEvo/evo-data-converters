lint:
	cd packages/common && uv run --only-dev ruff check ../..
	cd packages/common && uv run --only-dev ruff format --check ../..

lint-fix:
	cd packages/common && uv run --only-dev ruff check --fix ../..
	cd packages/common && uv run --only-dev ruff format ../..
# e.g. make create-converter ARGS="--converter-type foo --export-support 'Import only'"
create-converter:
	cd packages/common && uv run --only-dev python scripts/create_converter.py $(ARGS)

test:
	@set -e; \
	for pkg in packages/*/; do \
		echo "=== $$pkg ==="; \
		( cd "$$pkg" && uv sync && uv run pytest tests; ec=$$?; [ $$ec -eq 0 ] || [ $$ec -eq 5 ] ); \
	done

test-common:
	cd packages/common && uv sync && uv run pytest tests

test-duf:
	cd packages/duf && uv sync && uv run pytest tests

test-gocad:
	cd packages/gocad && uv sync && uv run pytest tests

test-image:
	cd packages/image && uv sync && uv run pytest tests

test-obj:
	cd packages/obj && uv sync && uv run pytest tests

test-omf:
	cd packages/omf && uv sync && uv run pytest tests

test-resqml:
	cd packages/resqml && uv sync && uv run pytest tests

test-shp:
	cd packages/shp && uv sync && uv run pytest tests

test-ubc:
	cd packages/ubc && uv sync && uv run pytest tests

test-vtk:
	cd packages/vtk && uv sync && uv run pytest tests

test-xyz:
	cd packages/xyz && uv sync && uv run pytest tests

