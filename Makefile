lint:
	uv run --only-dev ruff check
	uv run --only-dev ruff format --check

lint-fix:
	uv run --only-dev ruff format

test:
	uv run pytest .

test-common:
	uv run --package evo-data-converters-common pytest packages/common/tests

test-duf:
	uv run --package evo-data-converters-duf pytest packages/duf/tests

test-gocad:
	uv run --package evo-data-converters-gocad pytest packages/gocad/tests

test-image:
	uv run --package evo-data-converters-image pytest packages/image/tests

test-obj:
	uv run --package evo-data-converters-obj pytest packages/obj/tests

test-omf:
	uv run --package evo-data-converters-omf pytest packages/omf/tests

test-resqml:
	uv run --package evo-data-converters-resqml pytest packages/resqml/tests

test-ubc:
	uv run --package evo-data-converters-ubc pytest packages/ubc/tests

test-vtk:
	uv run --package evo-data-converters-vtk pytest packages/vtk/tests

