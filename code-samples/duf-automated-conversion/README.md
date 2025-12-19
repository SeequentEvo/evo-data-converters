# Automated DUF file to Evo data converter

This workflow consists of a Windows batch script that first collects parameters provided by the user. The batch script then calls a Python script that performs the DUF to Evo geoscience object conversion. 

This workflow can be performed with no (or minimal) user interaction. To fully automate the workflow a user could set up the Windows Task Scheduler to trigger the workflow on a regular schedule.

## Prerequisites

- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- An installed copy of Deswik.CAD

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
   ```

2. Open a command prompt, navigate to this directory and install the dependencies:
   ```cmd
   uv sync
   ```
   No need to manually create a Python virtual environment - `uv` handles this automatically!

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
   --client-secret "<EVO_CLIENT_SECRET>" \
   --hub-url "<EVO_HUB_URL>" \
   --user-agent "<EVO_USER_AGENT>" \
   --epsg-code "<EPSG_CODE>" \
   --upload-path "optional/path/in/evo" \
   --combine-layers
```

Notes:
- `--duf-file` should point to the file you want to convert. The batch script copies the source to `temp\<name>.duf` before execution; you can point to any accessible path when running manually.
- `--upload-path` is optional; omit or pass an empty string to upload at the workspace root.
- `--combine-layers` is a flag; include it to enable combining objects into layers.

## How it works

1. The batch script reads configuration from `.env`
2. Copies the DUF file to a temporary folder
3. Uses `uv run` to execute the Python script with all dependencies automatically managed
4. The Python script receives all configuration via command-line arguments (no `.env` reading)
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
