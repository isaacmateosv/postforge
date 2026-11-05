# Security

## Reporting a vulnerability

Please report security problems **privately** through GitHub: the repository's **Security** tab →
**Report a vulnerability**. Do not open a public issue for a vulnerability, and never post a token,
`.env` file, WhatsApp session, Postiz export or screenshot containing one.

You can expect an acknowledgement within a few days. PostForge is maintained by one person, so fixes are
made on a best-effort basis.

## What the project keeps out of the repository

`.env`, `data/`, `exports/`, `logs/`, `run/`, `backups/`, `tunnel/`, WhatsApp VIP lists and migration
bundles are git-ignored, excluded from the installer package, and checked on every CI run
(`scripts/recheck.sh` fails if a private file or a credential pattern is tracked, and
`scripts/package.sh` refuses to build a package that contains one).

## If you ever commit a secret

Treat it as leaked: revoke or rotate it at the provider first (Meta, TikTok, Google, ngrok, Postiz),
then remove it from the repository. Rewriting history does not un-leak it.

## Supported versions

Only the latest release is supported.
