# Prefix home isolation

`DARLING_ISOLATED_HOME=1` opts into real Documents, Desktop, Downloads, Movies,
Music, Pictures and Public directories in `/Users/<login>` inside the prefix.
Only the exact value `1` enables it. The default retains XDG host-folder links.
The launcher passes the option to darlingserver even in root mode.

Use a fresh prefix. Conflicting files or symlinks, including parent directory
symlinks, cause startup to fail without removing those entries or following them.
Existing real directories and their contents survive restart. The isolated path
also omits the normal LinuxHome host alias. This controls home setup, not access
through Darling's general `/Volumes/SystemRoot` mapping.

The option is read at server startup; changing it on a later shell request cannot
reconfigure an already running server. Catalyst's `DARLING_APP_CONTAINER=1`
continues to be a separate per-app CoreFoundation feature: it chooses an app's
`Library/Containers/<id>/Data` home after prefix initialization. Prefix isolation
protects shells and non-bundle apps too and does not require that CF feature.

Native regression (no root, containers or Apple binaries):

```sh
python3 tests/isolated-home.py
```

It compiles the production setupUserHome function with a synthetic XDG lookup.
Fixtures are retained under `/tmp/isolated-home-test-*`. On parent 22b386c it
reports 4 failures / 5 tests; the exact-value/default control passes.
Container validation must separately write markers through all six guest home
folders, restart the prefix, and run qv-host-guard snapshot/verify around the run.
