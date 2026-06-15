# Automated DUF File to Evo Converter

This root-level sample demonstrates a non-interactive DUF-to-Evo workflow.

The batch script `convert_duf.bat` reads parameters from a `.env` file and then runs `publish_to_evo.py` to convert and publish geoscience objects.

Use this sample when you want to run DUF imports repeatedly with minimal user interaction (for example with Windows Task Scheduler).

## Prerequisites

- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- An installed copy of Deswik.Suite

### Install uv

Open a command prompt and run this command:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
Changing the [execution policy](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-7.4#powershell-execution-policies) allows running a script from the internet.

## Setup

Visit the [setup documentation](docs/SETUP.md) for instructions on how to find the parameters listed below.

1. Make a copy of the file `.env.example` and rename it `.env`. Fill in the required parameters and save the file:
   ```
   DUF_FILE_PATH=path\to\your\file.duf
   EVO_ORG_ID=your-org-id
   EVO_WORKSPACE_ID=your-workspace-id
   EVO_CLIENT_ID=your-client-id
   EVO_CLIENT_SECRET=your-client-secret
   EVO_HUB_URL=your-hub-url
   EVO_USER_AGENT=your-user-agent
   EVO_EPSG_CODE=your-epsg-code
   EVO_UPLOAD_PATH=optional/path/in/evo
   EVO_COMBINE_LAYERS=true
   ```

2. Open a command prompt, navigate to this directory and install the dependencies:
   ```cmd
   uv sync
   ```
   No need to manually create a Python virtual environment - `uv` handles this automatically!

## Sample Data Files

The `example-data` folder includes sample DUF files that you can use for testing:
- `Marlin Mapping v1.duf`
- `Marlin Stopes.duf`
- `Pit Mesh.duf`

These files can be referenced in your `.env` file or passed directly via the `--duf-file` argument.

## Usage

**Windows File Explorer**

Simply double-click the file `convert_duf.bat` in File Explorer.

**Command prompt**

Navigate to this directory and run this command:
```cmd
convert_duf.bat
```

**Manual Python execution**

If you prefer to bypass the Windows batch script, pass all required arguments explicitly:

```powershell
# From this folder (Windows PowerShell)
uv run publish_to_evo.py \
   --duf-file "temp\\YourFile.duf" \
   --org-id "<EVO_ORG_ID>" \
   --workspace-id "<EVO_WORKSPACE_ID>" \
   --client-id "<EVO_CLIENT_ID>" \
   --hub-url "<EVO_HUB_URL>" \
   --user-agent "<EVO_USER_AGENT>" \
   --epsg-code "<EPSG_CODE>" \
   --upload-path "optional/path/in/evo" \
   --combine-layers
```

Notes:
- `--duf-file` should point to the file you want to convert. The batch script copies the source to `temp\<name>.duf` before execution; you can point to any accessible path when running manually.
- `--upload-path` is optional; omit or pass an empty string to upload at the workspace root.
- `EVO_CLIENT_SECRET` can be provided as an environment variable instead of a command-line argument.
- `--combine-layers` enables combining, and `--no-combine-layers` disables it.
- In the batch workflow, `EVO_COMBINE_LAYERS` controls combine behavior. Defaults to `true`; set `false` or `0` to disable.

## How it works

1. The batch script reads configuration from `.env`
2. Copies the DUF file to a temporary folder
3. Uses `uv run` to execute the Python script with all dependencies automatically managed
4. The Python script receives all configuration via command-line arguments (no `.env` reading)
5. Converts and uploads the file to Evo
6. Saves detailed execution information to the log file
7. Cleans up temporary files

## Log Files

Check `log.txt` in this directory for detailed execution logs.

## Related Sample

For an interactive notebook workflow, see the sibling sample in `../duf-jupyter-conversion`.
