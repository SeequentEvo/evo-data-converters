# DUF to Evo Jupyter Conversion

This root-level sample demonstrates an interactive notebook workflow for converting and publishing DUF data to Evo.

It is useful when you want to explore conversion options step-by-step, select a file interactively, and inspect results inside a notebook.

## Contents

- `convert_duf.ipynb`: Main notebook workflow
- `start-here.bat`: Windows launcher that installs/updates `uv`, creates `.venv` (if needed), and opens the notebook
- `helpers/`: UI and conversion helper modules used by the notebook
- `example-data/`: Sample DUF files for testing

## Prerequisites

- Windows environment (DUF converter support is Windows-only)
- Python 3.10 to 3.12
- Installed Deswik.Suite
- .NET runtime required by your Deswik.Suite version
- `uv` (installed automatically by `start-here.bat` if missing)

## Quick Start (Recommended)

From Windows File Explorer, double-click `start-here.bat`.

The script will:
1. Ensure `uv` is installed (or update it)
2. Create `.venv` with `uv sync` if needed
3. Activate the virtual environment
4. Launch `jupyter notebook convert_duf.ipynb`

## Manual Setup

From this folder in a command prompt:

```cmd
uv sync
uv run jupyter notebook convert_duf.ipynb
```

## Sample Data Files

The `example-data` folder includes sample DUF files:
- `Marlin Mapping v1.duf`
- `Marlin Stopes.duf`
- `Pit Mesh.duf`

## Notes

- The notebook uses `ServiceManagerWidget` for Evo login and workspace selection.
- Install exact dependencies from `pyproject.toml` or `requirements.txt` if you are not using `uv sync`.
- For a non-interactive workflow suitable for scheduling, see `../duf-automated-conversion`.
