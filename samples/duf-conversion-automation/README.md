# DUF Converter for Evo

This tool converts DUF (Deswik Unified File) files and publishes them to an Evo workspace.

## Prerequisites

- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver

### Install uv

**Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or via pip:
```bash
pip install uv
```

## Setup

1. Copy `.env.example` to `.env` and fill in your credentials:
   ```
   DUF_FILE_PATH=path\to\your\file.duf
   EVO_ORG_ID=your-org-id
   EVO_WORKSPACE_ID=your-workspace-id
   EVO_CLIENT_ID=your-client-id
   EVO_CLIENT_SECRET=your-client-secret
   EVO_HUB_URL=your-hub-url
   EVO_USER_AGENT=your-user-agent
   EVO_EPSG_CODE=32650
   EVO_UPLOAD_PATH=optional/path/in/evo
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. No need to create a virtual environment - `uv` handles this automatically!

## Usage

### Windows
Simply run the batch script (double-click it in Windows Explorer or run from command line):
```cmd
convert_duf.bat
```

### Manual Python execution
```bash
uv run publish_to_evo.py
```

## How it works

1. The batch script reads configuration from `.env`
2. Copies the DUF file to a temporary folder
3. Uses `uv run` to execute the Python script with all dependencies automatically managed
4. The Python script reads the DUF file path and credentials from `.env`
5. Converts and uploads the file to Evo
6. Saves detailed execution information to the log file
7. Cleans up temporary files

## Sample Data Files

The `data` folder includes sample DUF files that you can use for testing:
- `Marlin Mapping v1.duf`
- `Marlin Stopes.duf`
- `Pit Mesh.duf`

These files can be referenced in your `.env` file or passed directly via the `--duf-file` argument.

## Log Files

Check `log.txt` in this directory for detailed execution logs.
