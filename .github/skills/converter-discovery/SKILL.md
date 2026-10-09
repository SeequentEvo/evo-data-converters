---
name: converter-discovery
description: "Use when starting a new Evo data converter and you need to understand the input file format before writing code. Inspects sample data, identifies the format, finds a suitable open-source reader library (license-checked), and maps the data to Evo geoscience object types. Use for: 'build a converter for X format', 'what Evo object does this data map to', 'which library reads this file', analysing sample data. Second phase of building a converter."
---

# Converter discovery

The package is already scaffolded and the user should have dropped a sample file in
`packages/<type>/tests/data/`. Before writing any parsing or mapping code, produce a
**discovery summary** that answers three questions:

1. What is the input format, precisely?
2. How will we read it (which open-source library, or a custom parser)?
3. Which Evo geoscience object type(s) does the data map to?

Do this phase actively — read the sample data, run small inspection commands, and check library
licenses.

## 1. Gather inputs

- Look for the sample file in `packages/<type>/tests/data/` (where the scaffold phase asked the
  user to place it). If it isn't there, ask the user for the format name and a sample file, and
  have them drop it in that folder.
- If no sample is available, work from the format specification and the user's description, and
  note that assumptions must be validated later against real data.

## 2. Identify the format

Inspect the sample rather than guessing:

- Text vs binary: check the first bytes / magic number.
  ```shell
  file <sample>
  head -c 256 <sample> | xxd | head
  ```
- For text/tabular data, look at the header row, delimiter, column meaning, and units.
- For binary data, look for a documented header, record layout, endianness, and version.
- Record: geometry kind (points, lines, surfaces/meshes, grids/volumes, block models),
  attributes/properties per element, coordinate system hints, and units.

## 3. Choose how to read it

Prefer a well-maintained open-source library over a hand-rolled parser when one exists.

- Search PyPI / GitHub for readers for the format.
- **Check the license** — must be compatible with this repo's Apache 2.0 (permissive licenses
  such as MIT, BSD, Apache are fine; copyleft such as GPL is not). Record the license.
- Prefer libraries that return NumPy arrays / PyArrow tables, since those map cleanly onto the
  parquet-hash / `data_client.save_table` upload pattern.
- If no suitable library exists, plan a custom parser (see `gocad` for a binary example and
  `xyz` for a text example).

## 4. Map to Evo geoscience objects

Decide the target object type(s) using the cheatsheet in
[`references/geoscience-objects.md`](references/geoscience-objects.md). Confirm the class exists
in the installed `evo_schemas` package (versions are suffixed, e.g. `Pointset_V1_3_0`):

```shell
uv run python -c "import evo_schemas.objects as o; print([n for n in dir(o) if not n.startswith('_')])"
```

Map each source concept to an Evo concept: geometry → object coordinates/indices; per-element
values → `ContinuousAttribute` / `CategoryAttribute`; spatial extent → `BoundingBox`; spatial
reference → `Crs`.

## 5. Produce the discovery summary

Report back (and keep for the mapping phase):

- **Format**: name, text/binary, structure, version, units.
- **Reader**: chosen library + version + license, or "custom parser" with a sketch of the steps.
- **Intermediate representation**: what `read_<type>_file` will return (e.g. a dataclass with
  `points: np.ndarray[N,3]` and `attributes: dict`).
- **Target Evo object(s)**: the `evo_schemas` class(es) and how source fields map to them.
- **Open questions / assumptions** to validate against real sample data.

## Next

Proceed to [`map-to-evo-schemas`](../map-to-evo-schemas/SKILL.md).
