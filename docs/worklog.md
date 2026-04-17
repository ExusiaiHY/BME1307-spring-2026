# BME1307 Worklog

## 2026-04-17

### Part 2 readiness check

- Confirmed the local dataset is present in `Breast-ultrasound-samples/Ultrasound Samples`.
- Counted `120` ultrasound images and `120` pathology labels.
- Verified the pathology label distribution is `74` negatives and `46` positives.
- Confirmed the Python environment can now read `pathology.xlsx` after installing `openpyxl`.

### Tooling status

- Initial shell check did not find `MATLAB` on `PATH`.
- `Octave` is not installed on this machine.
- The BUSAT official download URL listed in the course materials could not be resolved under `www.tamps.cinvestav.mx` on `2026-04-17`.
- The alternate host `tamps.cinvestav.mx` responded with `403 Acceso restringido`, including with a browser-like user agent.
- BUSAT is therefore currently blocked by the remote host rather than by the local environment.

### Notion sync status

- The provided Notion page is reachable over the web.
- This environment does not currently have a Notion API client, token, or another authenticated write path, so direct write-back to Notion is blocked for now.
- Until a writable Notion integration is provided, this file will be used as the source-of-truth worklog and can be synced later.

### BUSAT re-check

- Confirmed MATLAB is installed at `/Applications/MATLAB_R2026a.app/bin/matlab`.
- The `matlab` executable is not on the current shell `PATH`.
- No `BUSAT`, `autosegment.m`, or related add-on content was found in the repository, common user add-on directories, or the MATLAB toolbox cache.
- Current conclusion: MATLAB installation is complete, but BUSAT is not yet discoverable as an installed and callable toolbox from this environment.
