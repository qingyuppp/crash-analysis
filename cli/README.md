# Crash Analysis CLI

`cra` provides deterministic pre-analysis for a vmcore. It is intended to run
inside the existing analysis container; Jenkins/Docker orchestration remains
outside this package.

## Manual container usage

Install the local CLI in the image or an interactive analysis container:

```bash
cd /workspace/crash-analysis/cli
python3 -m pip install --no-deps -e .
```

Run deterministic collection and classification into an isolated output
directory. `crash`, `rpm2cpio`, and `cpio` must already be available in the
container.

```bash
cra vmcore collect \
  --vmcore /data/input/vmcore \
  --debuginfo /data/input/debuginfo.rpm \
  --kernel /data/input/kernel \
  --output-dir /data/output

cra vmcore classify --collection /data/output/collection.json
```

The current package also carries the installable skill entry point:

```bash
cra skills list
cra skills install crash-analysis --target joycode
```

`joycode` installs to `/root/.joycode/skills` (or `JOYCODE_SKILLS_DIR`), while
`codex` installs to `$CODEX_HOME/skills` or `~/.codex/skills`. `custom` needs
an explicit `--skills-dir`. Use `--force` only when replacing an installed
skill; `uninstall` only removes skills recorded by `cra`.
