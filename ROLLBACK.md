# Rollback procedure

The current stable code/configuration has a local snapshot under
`run/rollback/`. The snapshot intentionally excludes `.env`, Postgres, Redis,
WhatsApp session data, media, logs, and runtime queues.

## Verify the snapshot

```bash
cd ~/postforge
find run/rollback -name MANIFEST.txt -print
cat run/rollback/YYYYMMDD-HHMMSS/MANIFEST.txt
```

Never copy `.env` into a snapshot or commit it.

## Restore

Replace `YYYYMMDD-HHMMSS` with the snapshot directory shown above:

```bash
./scripts/rollback.sh run/rollback/YYYYMMDD-HHMMSS
```

The script asks for confirmation, stops the stack, restores code and
configuration and saved local image tags (when `images.json` exists), starts the stack, and leaves credentials and runtime data in place. Old local images must still exist; avoid pruning them until the update is verified. Rollback does not reverse database migrations; export a backup before upgrades that change the database. Verify the result:

```bash
./postforge.sh status
python3 scripts/lib/machine_state.py --json
```

## Rollback acceptance

A rollback is complete only when:

```text
Machine state: on
Postiz: reachable
Scheduler: polling Temporal
WhatsApp: open
Tunnel: reachable
```

The menu header should say **Ready to post** and `./postforge.sh status` should list every service
as healthy. If it says **Needs attention**, choose **Restore All Services** and rerun
`./postforge.sh status`. Inspect `logs/tray.log`, `logs/wa-inbox.log`, and
the relevant `docker logs --since 30m <container>` output before declaring the
rollback stable.

Do not treat a successful container start alone as proof of stability: scheduled
posts require the Temporal worker, WhatsApp requires an `open` connection, and
the public URL must answer after the tunnel starts.

If the stack does not become healthy, stop it and restore the previous
`.env` only if you intentionally changed credentials. Do not delete Postgres,
Redis, or WhatsApp data during rollback.

## Recovery hierarchy

1. Use the rollback snapshot for code/configuration regressions.
2. Keep the existing `.env` unless credentials were intentionally rotated.
3. Keep Postgres, Redis, media, and WhatsApp state.
4. Restore Postiz account data only from a separately created private export.
5. Relink WhatsApp only if its session state is deliberately lost.
