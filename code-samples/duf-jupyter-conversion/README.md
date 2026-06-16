# DUF to Evo Jupyter Conversion

This root-level sample demonstrates an interactive notebook workflow for converting and publishing DUF data to Evo.

It is useful when you want to explore conversion options step-by-step, select a file interactively, and inspect results inside a notebook.

## Contents

- `convert_duf.ipynb`: Main notebook workflow
- `start-here.bat`: Windows launcher that tries setup with `uv`, falls back to `pip` if `uv` setup fails, and opens the notebook
- `helpers/`: UI and conversion helper modules used by the notebook
- `example-data/`: Sample DUF files for testing

## Prerequisites

- Windows environment (DUF converter support is Windows-only)
- Python 3.10 to 3.12
- Installed Deswik.Suite
- .NET runtime required by your Deswik.Suite version
- `uv` for the recommended setup, or `pip` for automatic fallback setup

## Quick Start (Recommended)

From Windows File Explorer, double-click `start-here.bat`.

If the project is stored in a deep folder path and Windows Long Path support is disabled, dependency installation can fail. The launcher now warns about this before setup starts; if you see that warning, either enable Windows Long Paths or move this folder closer to the drive root.

The script will:
1. Ensure `uv` is installed (or update it)
2. Run `uv sync` to create or update `.venv`
3. If `uv` setup fails, create or update `.venv` with Python's built-in `venv` module and `pip`
4. Activate the virtual environment
5. Launch `jupyter notebook convert_duf.ipynb`

Tip: force `pip` setup instead of `uv`
- Run `start-here.bat --force-pip` to skip `uv` and use `pip` directly.
- Or set `FORCE_PIP_SETUP=1` before launching the script (for example: `set FORCE_PIP_SETUP=1 && start-here.bat`).

## Manual Setup

From this folder in a command prompt:

```cmd
uv sync
uv run jupyter notebook convert_duf.ipynb
```

Or, using `pip`:

```cmd
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
jupyter notebook convert_duf.ipynb
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
