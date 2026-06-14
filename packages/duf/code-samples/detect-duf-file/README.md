# Detect DUF File Type (Notebook Sample)

This sample demonstrates how to detect whether a file is a valid Deswik Unified File (DUF).

The workflow is implemented in [detect-duf-file.ipynb](detect-duf-file.ipynb).

## Prerequisites

- Python 3.10+
- Windows environment (DUF package support is Windows-only)
- Installed Deswik.Suite
- .NET runtime required by your Deswik.Suite version
- Python packages:
  - `evo-data-converters-duf`
  - `jupyter`

Install with pip:

```bash
pip install evo-data-converters-duf jupyter
```

## Sample Files

Input files are included under [data/input](data/input):

- `polyline_in_layer_no_attrs.duf` (expected DUF)
- `not-duf.duf` (expected non-DUF)

## What The Notebook Does

1. Imports `is_duf` from `evo.data_converters.duf`.
2. Builds paths to sample files in [data/input](data/input).
3. Calls `is_duf(path)` for each file.
4. Prints whether each file is recognized as DUF.

## Run

From this folder, start Jupyter and open the notebook:

```bash
jupyter notebook detect-duf-file.ipynb
```
