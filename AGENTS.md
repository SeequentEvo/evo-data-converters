# AGENTS.md — Building Evo data converters

This repository converts data from third-party geoscience formats into **Evo geoscience
objects** and publishes them to Evo. This file orients AI coding agents (and humans) who are
building a **new converter**. It is tool-agnostic: any agent that reads `AGENTS.md` can follow
it, and the referenced skill files under [`.github/skills/`](.github/skills/) contain the
detailed, step-by-step workflows.

## What this repo is

- A `uv` workspace. Each supported format is a package under `packages/<type>/` that builds on
  the shared framework in [`packages/common`](packages/common/README.md).
- Existing converters to learn from: `xyz` (point set from CSV/text), `omf` (multiple object
  types + export + block model), `gocad` (binary), `resqml`, `vtk`, `shp`, `image`, `ubc`,
  `obj`, `duf`.
- A scaffolding CLI, `create-converter`, that generates a complete, ready-to-implement package.

## The build workflow

Building a converter has four phases. Each has a dedicated skill — open the linked `SKILL.md`
for the full procedure, checklists, and examples.

1. **Scaffold** — [`.github/skills/scaffold-converter/SKILL.md`](.github/skills/scaffold-converter/SKILL.md)
   Run `create-converter` to generate the package and wire it into the workspace. The template
   creates `packages/<type>/tests/data/`; have the user drop their sample file there.
2. **Discovery** — [`.github/skills/converter-discovery/SKILL.md`](.github/skills/converter-discovery/SKILL.md)
   Inspect the sample data in `packages/<type>/tests/data/`, identify the input format, choose an
   open-source reader library (license-checked), and decide which Evo geoscience object type(s)
   the data maps to.
3. **Map to Evo schemas** — [`.github/skills/map-to-evo-schemas/SKILL.md`](.github/skills/map-to-evo-schemas/SKILL.md)
   Implement the reader and the geoscience-object builder: parse the file, then construct
   `evo-schemas` objects and upload referenced arrays.
4. **Test** — [`.github/skills/test-converter/SKILL.md`](.github/skills/test-converter/SKILL.md)
   Replace the placeholder tests with real ones, then run tests, linting, and type checks.

For an end-to-end run, use the orchestrator skill
[`.github/skills/build-evo-converter/SKILL.md`](.github/skills/build-evo-converter/SKILL.md),
which sequences the four phases above.

> Export (Evo → file) is a documented follow-up. Scaffold with "Import and Export" to generate
> the exporter stubs, but implement and verify the import path first.

## Converter architecture (what you implement)

`create-converter` generates these files with `NotImplementedError` stubs. You fill in the two
marked with **→**; the rest is already wired for you:

```
packages/<type>/src/evo/data_converters/<type>/
├── __init__.py                     # exports convert_<type> (+ exporters)
└── importer/
    ├── <type>_reader.py            # → implement read_<type>_file(filepath); defines
    │                               #   <TYPE>InvalidDataError, <TYPE>DataFileIOError
    ├── utils.py                    # → implement get_geoscience_object_from_<type>(...)
    └── <type>_to_evo.py            # convert_<type>(...) entry point — already wired
```

- `convert_<type>(...)` already creates the Evo clients, resolves the CRS, calls
  `get_geoscience_object_from_<type>`, and publishes via `publish_geoscience_objects_sync`.
  It returns `list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata]`. **Don't change, reorder,
  or remove the standard parameters** — but you _may_ add new **optional keyword-only** params
  (after the `*`, with defaults) for runtime choices such as geometry grouping.
- `get_geoscience_object_from_<type>(...)` returns a single object, or a `list[...]` when one
  file maps to several objects; `convert_<type>` wraps the result into the published list.
- `read_<type>_file(filepath)` parses the file into whatever intermediate representation you
  choose; raise `<TYPE>DataFileIOError` on I/O problems and `<TYPE>InvalidDataError` on bad data.
- `get_geoscience_object_from_<type>(data_client, filepath, coordinate_reference_system, tags)`
  turns the parsed data into an `evo-schemas` object: upload large arrays with
  `data_client.save_table(...)` (or the parquet-hash pattern), set the bounding box, CRS, and
  tags, and return a subclass of `BaseSpatialDataProperties_V1_0_1`.

## Key commands

```shell
uv sync --all-packages --all-extras   # set up the workspace
uv run create-converter               # scaffold a new converter (interactive)
uv sync                               # install the newly generated package
make test-<type>                      # run the new converter's tests
uv run ruff check                     # lint (line length 120)
uv run mypy packages/<type>           # type check
```

## Framework APIs (from `evo.data_converters.common`)

- `create_evo_object_service_and_data_client(evo_workspace_metadata=..., service_manager_widget=...)`
- `publish_geoscience_objects_sync(objects, object_service_client, data_client, upload_path, overwrite_existing_objects)`
- `crs_from_any(...)`, `crs_from_epsg_code(...)` (in `evo.data_converters.common.crs`)
- `data_client.save_table(pyarrow_table)` and `data_client.cache_location` for referenced data

## External references

- **Evo schemas** (geoscience object types): <https://github.com/SeequentEvo/evo-schemas>
  (`uv add evo-schemas`; imported as `evo_schemas`)
- **Evo Python SDK** (clients, auth, publishing): <https://github.com/SeequentEvo/evo-python-sdk>
- **Developer Portal**: <https://developer.seequent.com/docs/data-structures/geoscience-objects/>

## Guardrails

- **Never commit secrets.** Access tokens, client IDs, org/workspace IDs, and hub URLs are
  user-supplied at runtime — keep them out of code, tests, and sample data.
- **Stay within the package pattern.** Add new format logic under `packages/<type>/`; put
  genuinely shared helpers in `packages/common`. Don't alter the standard `convert_<type>`
  parameters or return type (adding optional keyword-only params is fine).
- **Keep the Apache 2.0 license header** on every new source file (the template includes it).
- **Prefer small, real sample data** committed under the package's `code-samples`/`tests` for
  reproducible tests; confirm licensing before committing third-party data.
- **Run `make test-<type>`, `ruff`, and `mypy`** before considering a converter done.
