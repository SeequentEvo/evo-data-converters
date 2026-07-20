---
applyTo: "code-samples/**"
---
# Code samples and notebooks

Code samples demonstrate how to use a converter end-to-end. They live in
`code-samples/` and `packages/<format>/code-samples/`. Each sample should be
runnable standalone by a developer with no prior knowledge of the Evo platform.

See `code-samples/duf-automated-conversion/` for a script reference and
`code-samples/duf-jupyter-conversion/` for a Jupyter notebook reference.

---

## Required conventions

### Credentials — never hardcode

Always load workspace credentials from environment variables or a `.env` file.
Never hardcode `org_id`, `hub_url`, `workspace_id`, `client_id`, or
`client_secret`.

```python
import os
from evo.data_converters.common import EvoWorkspaceMetadata

metadata = EvoWorkspaceMetadata(
    org_id=os.environ["EVO_ORG_ID"],
    hub_url=os.environ["EVO_HUB_URL"],
    workspace_id=os.environ["EVO_WORKSPACE_ID"],
    client_id=os.environ["EVO_CLIENT_ID"],
    client_secret=os.environ["EVO_CLIENT_SECRET"],
)
```

For notebooks, document the required environment variables clearly at the top
cell and point the reader to [Apps and Tokens](https://developer.seequent.com/docs/guides/getting-started/apps-and-tokens/)
for how to obtain them.

### Full convert-and-publish flow

Every sample must show the complete flow:
1. Load credentials into `EvoWorkspaceMetadata`
2. Call the converter (e.g. `convert_omf(filepath, evo_workspace_metadata=metadata)`)
3. Print or display the resulting published object metadata

### Package management

Use `uv` for dependency management. Each sample directory must have a
`pyproject.toml` that lists its own dependencies. Do not rely on the root
workspace's environment being active.

---

## Jupyter notebook conventions

- The first cell must be a Markdown cell explaining what the notebook does and
  listing prerequisites (credentials, input files).
- Use one cell per logical step: load data, configure metadata, convert,
  display results.
- Display results with `print` or `IPython.display` — do not rely on
  implicit cell output for critical information.
- Keep helper code in a `helpers/` subdirectory (see
  `code-samples/duf-jupyter-conversion/helpers/`) rather than inline in cells.
- Test that the notebook runs end-to-end with `uv run jupyter nbconvert
  --to notebook --execute <notebook>.ipynb` before committing.

---

## Script conventions

- Scripts must be runnable with `uv run python <script>.py`.
- Include a `if __name__ == "__main__":` guard.
- Accept file paths and optional arguments via `argparse`, not hardcoded paths.
- Print a short summary of what was published (object names, types, count).

---

## README requirement

Each sample directory must have a `README.md` that covers:
1. What the sample does
2. Prerequisites (credentials, required files, Python version)
3. How to run it (exact commands)
4. Expected output

---

## Example data

- Include small example input files in `example-data/` where possible.
- Do not include real customer or proprietary data.
- Document the source and licence of any included data files in the README.
