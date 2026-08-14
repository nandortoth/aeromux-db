# Self-hosted build & release

This directory contains the tooling that builds the aeromux-db database and publishes
it as a GitHub Release, run **weekly on a self-hosted server** by a `systemd` timer
rather than by GitHub Actions.

## Why this exists

The database build downloads six public data sources. On GitHub-hosted runners some of
those downloads fail intermittently — outbound connections from the runner IP ranges
time out — so scheduled builds kept failing at the download step. A build from an
ordinary (e.g. self-hosted) egress IP avoids this. Rather than run a GitHub-registered
self-hosted runner (a standing security liability for a public repo), the build runs as
a plain scheduled script that publishes the release with the GitHub CLI. Released
artifacts are unchanged for consumers.

## What's here

| File | Purpose |
|---|---|
| `build-and-release.sh` | The job: update, build, publish the release, prune old ones. |
| `systemd/aeromux-db.service` | Oneshot unit that runs the script as the `aeromux-db` account. |
| `systemd/aeromux-db.timer` | Weekly schedule (Monday 03:00 UTC, catch-up on boot). |
| `credentials.env.example` | Template for the secret env file (token + monitoring URL). |
| `config.env.example` | Template for the non-secret tunables. |

## Requirements

- **Debian 13 (trixie) or newer** (systemd + glibc + apt). This is the only supported
  platform.
- 2 vCPU / 4 GB RAM / ~20 GB disk. The build peaks around ~2 GB RAM.
- Outbound HTTPS. No inbound ports.
- `git`, `curl`, `gh` (GitHub CLI), and `uv`.

## Install

Debian doesn't ship `sudo` in a default install, so these steps are written to run **as
root** — log in as root or `su -` first; the commands need no `sudo`. To run a command
as the unprivileged `aeromux-db` account we use `runuser` (from `util-linux`, present by
default). If you prefer `sudo`, `apt install sudo`, add your user to the `sudo` group,
and prefix each command with `sudo`.

### 1. Prerequisites

```bash
apt update && apt full-upgrade -y
apt install -y git curl ca-certificates qemu-guest-agent
# qemu-guest-agent is a static, activation-based unit (no `enable` needed); it
# auto-starts on boot when the VMM guest-agent channel is present. Start it now:
systemctl start qemu-guest-agent
apt install -y unattended-upgrades && dpkg-reconfigure -plow unattended-upgrades

# Persist journald across reboots (otherwise service logs are volatile).
mkdir -p /var/log/journal
systemd-tmpfiles --create --prefix /var/log/journal
systemctl restart systemd-journald

# GitHub CLI (official apt repo)
mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/github-cli.list > /dev/null
apt update && apt install -y gh
```

### 2. Service account + checkout

```bash
adduser --system --group --no-create-home --home /opt/aeromux-db \
    --shell /usr/sbin/nologin aeromux-db

# /opt is root-owned; create the checkout dir owned by the account, then clone.
install -d -o aeromux-db -g aeromux-db /opt/aeromux-db
runuser -u aeromux-db -- git clone https://github.com/aeromux/aeromux-db.git /opt/aeromux-db

# uv for the service account (lands in /opt/aeromux-db/.local/bin).
runuser -u aeromux-db -- env HOME=/opt/aeromux-db sh -c \
    'curl -LsSf https://astral.sh/uv/install.sh | sh'
```

### 3. Credentials + config

`credentials.env` needs two values:

- **`GH_TOKEN`** (required) — a **fine-grained PAT**: GitHub → Settings → Developer
  settings → Fine-grained tokens → *Generate new token*. Set **Repository access** to
  only `aeromux/aeromux-db` and **Permissions → Repository → Contents** to
  *Read and write* (that is all release publishing needs). Set an expiration and note
  it for rotation.
- **`HEALTHCHECKS_URL`** (optional monitoring) — sign up for a free account at
  [healthchecks.io](https://healthchecks.io) (or self-host it), create a **check** with
  a weekly schedule and a grace period of at least 2 hours, and copy its **ping URL**
  (looks like `https://hc-ping.com/<uuid>`). The script pings it at start and on
  success, and on failure posts the tail of the run log; a *missed* weekly ping also
  alerts you if the VM never ran at all. Delete the line to disable monitoring.

Then create the files from the templates and fill in the values:

```bash
install -d -m 750 -o root -g root /etc/aeromux-db
cp /opt/aeromux-db/scripts/credentials.env.example /etc/aeromux-db/credentials.env
cp /opt/aeromux-db/scripts/config.env.example      /etc/aeromux-db/config.env
chmod 600 /etc/aeromux-db/credentials.env
chmod 644 /etc/aeromux-db/config.env
editor /etc/aeromux-db/credentials.env   # set GH_TOKEN (and HEALTHCHECKS_URL, or delete it)
```

### 4. Install and enable the units

```bash
cp /opt/aeromux-db/scripts/systemd/aeromux-db.service /etc/systemd/system/
cp /opt/aeromux-db/scripts/systemd/aeromux-db.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now aeromux-db.timer
```

**Copy** the units, do not `systemctl link` them from the checkout (see [Rules](#rules--gotchas)).

### 5. Dry run

```bash
systemctl start --no-block aeromux-db.service   # --no-block: don't tie up the prompt
journalctl -fu aeromux-db.service               # watch progress live
```

`aeromux-db.service` is `Type=oneshot`, so a plain `systemctl start` **blocks until the
build finishes** (a few minutes); `--no-block` queues it and returns immediately.
Confirm a release appears at <https://github.com/aeromux/aeromux-db/releases> and, if
`HEALTHCHECKS_URL` is set, that the check shows a success ping.

## Configure

Two files under `/etc/aeromux-db/`:

- **`credentials.env`** (`0600`) — `GH_TOKEN` (required) and `HEALTHCHECKS_URL`
  (a capability URL; treat as secret).
- **`config.env`** (`0644`) — `KEEP` (releases to retain, default 10), `RELEASE`
  (release number within the ISO week), `GH_REPO` (publish target; defaults to the
  checkout's origin remote), `MIN_AIRCRAFT` (aircraft-count floor below which the
  build is not published, default 500000).

> **Both are systemd `EnvironmentFile`s: use full-line comments only.** systemd does
> not strip trailing/inline comments, so `KEEP=10  # note` sets `KEEP` to
> `10  # note` and breaks the build. Put comments on their own lines.

The schedule (weekly, Monday 03:00 UTC) lives in `aeromux-db.timer`, not in these files
— edit the `OnCalendar` line there to change it. Values can also be passed as CLI flags
for ad-hoc runs: `--release N`, `--keep N`, `--no-pull`.

## Operate

Run these as root (or with `sudo` if you installed it).

| Task | Command |
|---|---|
| Next run / schedule | `systemctl list-timers aeromux-db.timer` |
| Last run status | `systemctl status aeromux-db.service` |
| Logs | `journalctl -u aeromux-db.service` |
| Run now (blocks until done) | `systemctl start aeromux-db.service` |
| Run now (fire-and-forget) | `systemctl start --no-block aeromux-db.service` |

**Recovery**

| Situation | Action |
|---|---|
| Transient upstream failure | Re-run the service; it skips if the release already exists. |
| Build failed (red check) | Read `journalctl -u aeromux-db.service`; no release is created, so re-run after fixing. |
| "refusing to publish" | A sanity check rejected the build (empty count, aircraft below `MIN_AIRCRAFT`, version mismatch). The database is wrong, not the check — investigate the source data before overriding. |
| Missed run (VM was down) | `Persistent=true` runs it on next boot, or trigger manually. |
| Token expired/revoked | Update `GH_TOKEN` in `credentials.env`; re-run the service. |
| Disk full | `runuser -u aeromux-db -- rm -rf /opt/aeromux-db/.cache/uv` |

## Rules & gotchas

- **Never hand-edit the checkout at `/opt/aeromux-db`.** Each run does
  `git reset --hard origin/main`, which silently discards local changes. Make changes in
  git; the next run pulls them.
- **Copy the units, never `systemctl link`.** The checkout is writable by the
  `aeromux-db` account; a unit run from a non-root-writable path lets that account
  escalate to root. Copies in `/etc/systemd/system/` are root-owned. Re-copy +
  `daemon-reload` when the units change (the script auto-updates; units do not).
- **Calibrate `MemoryMax`.** After the first run, read
  `systemctl show -p MemoryPeak aeromux-db.service` and set `MemoryMax` ~20% above it.
- **Protect the `main` branch.** `Contents: write` also permits pushing to the repo, so
  branch protection bounds a leaked token.

## Reuse in a fork

The script hardcodes no repository — `gh` publishes to the checkout's `origin` remote.
Clone your fork, use a PAT scoped to it, and releases go to your fork. To publish
somewhere other than origin, set `GH_REPO=owner/repo` in `config.env`.

---

Licensed under GPL-3.0-or-later (see [LICENSE.md](../LICENSE.md)).
