# Contributing

PostForge is maintained by Isaac Mateo Sarzosa Valencia (`isaacmateosv`).

## Checks

```bash
./scripts/recheck.sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_operations.py
./tray/build.sh --portable
./scripts/verify-artifacts.sh
```

Use `--verify-ui` to check native window localization and update-check result states.
`--check-updates-once -projectDir /absolute/project/path` runs one read-only live update check.

## Ground rules

- Automation creates drafts or waits for explicit approval; never publish implicitly.
- Keep credentials, media, databases, private exports and session state out of Git.
- Python host scripts use the standard library and support Python 3.9.
- Keep English and Ecuadorian Spanish app copy synchronized.
- Update documentation and the changelog with visible changes.

## Releases

`main` is the stable source. `VERSION`, its changelog section and the `v*` tag must match.
Push a version tag after source, UI and artifact checks pass. GitHub Actions builds and
checks the installer, then publishes its package and SHA-256 checksum.

The first release is `v1.0.0`. Telegram belongs to release 2; see [ROADMAP.md](ROADMAP.md).
