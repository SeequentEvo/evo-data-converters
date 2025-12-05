lint:
	uv run --only-dev ruff check
	uv run --only-dev ruff format --check

lint-fix:
	uv run --only-dev ruff format

test:
	uv run pytest .

test-common:
	uv run --package evo-data-converters-common pytest packages/common/tests

test-gef:
	uv run --package evo-data-converters-gef pytest packages/gef/tests

test-gocad:
	uv run --package evo-data-converters-gocad pytest packages/gocad/tests

test-omf:
	uv run --package evo-data-converters-omf pytest packages/omf/tests

test-resqml:
	uv run --package evo-data-converters-resqml pytest packages/resqml/tests

test-ubc:
	uv run --package evo-data-converters-ubc pytest packages/ubc/tests

test-vtk:
	uv run --package evo-data-converters-vtk pytest packages/vtk/tests

