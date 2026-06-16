# Convert DUF to Evo (Notebook Sample)

This sample demonstrates how to authenticate with Evo and publish geoscience objects from a Deswik Unified File (DUF).

The workflow is implemented in [convert-duf.ipynb](convert-duf.ipynb).

## Prerequisites

- Python 3.10+
- Windows environment (DUF converter support is Windows-only)
- Installed Deswik.Suite
- .NET runtime required by your Deswik.Suite version
- Python packages:
  - `evo-data-converters-duf`
  - `evo-notebooks` (for `ServiceManagerWidget`)
  - `jupyter`

Install with pip:

```bash
pip install evo-data-converters-duf evo-notebooks jupyter
```

## Sample Files

Input DUF examples are included under [data/input](data/input):

- `Marlin Mapping v1.duf`
- `Marlin Stopes.duf`
- `Pit Mesh.duf`

## What The Notebook Does

1. Logs in to Evo using `ServiceManagerWidget`.
2. Selects a DUF file from [data/input](data/input).
3. Sets an EPSG code for the coordinate reference system.
4. Calls `convert_duf(...)` from `evo.data_converters.duf.importer`.
5. Prints metadata for published objects.

## Run

From this folder, start Jupyter and open the notebook:

```bash
jupyter notebook convert-duf.ipynb
```

## Notes

- Set `client_id="your-client-id"` in the login cell.
- `combine_objects_in_layers=True` can merge compatible objects in the same layer.
- Some DUF geometry types are not supported yet and will be reported as warnings.
