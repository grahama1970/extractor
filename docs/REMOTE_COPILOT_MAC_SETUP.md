# Remote Copilot Automation — macOS Setup (No sudo)

This guide sets up key‑based SSH and macOS Accessibility permissions so the Comet + GitHub Copilot AppleScript automation can run from a remote Linux workstation.

Applies to: user `robert` on the Mac at `100.84.184.37` (adjust as needed).

## Overview

- Authentication: dedicated SSH key (ed25519), no agent required.
- Accessibility: allow `osascript` (Terminal/Script Editor) and `Comet` under macOS Privacy & Security.
- Automation: UI‑driven (not an API), so prompts won’t be bot‑blocked.

## 1) Generate a dedicated SSH key (workstation)

```bash
ssh-keygen -t ed25519 -C "comet-copilot-automation" \
  -f ~/.ssh/id_ed25519_comet -N ''
```

Optional config entry for convenience:

```bash
printf '%s\n' \
'Host macbook-copilot' \
'  HostName 100.84.184.37' \
'  User robert' \
'  IdentitiesOnly yes' \
'  IdentityFile ~/.ssh/id_ed25519_comet' \
>> ~/.ssh/config
```

## 2) Install the public key on the Mac (one‑time)

Either use `ssh-copy-id`:

```bash
ssh-copy-id -i ~/.ssh/id_ed25519_comet.pub robert@100.84.184.37
```

Or copy + append manually (no sudo):

```bash
scp ~/.ssh/id_ed25519_comet.pub robert@100.84.184.37:~/id_ed25519_comet.pub
ssh robert@100.84.184.37 \
  'umask 077; mkdir -p ~/.ssh; cat ~/id_ed25519_comet.pub >> ~/.ssh/authorized_keys; \
   rm ~/id_ed25519_comet.pub; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys'
```

Verify key‑only login (no password prompt):

```bash
ssh -i ~/.ssh/id_ed25519_comet robert@100.84.184.37 'echo ok'
# or, with config:
ssh macbook-copilot 'echo ok'
```

## 3) Grant macOS Accessibility + Automation (on the Mac)

System Settings → Privacy & Security:

- Accessibility → enable (allow):
  - Terminal (or Script Editor)
  - Comet
- Automation → under Terminal (or Script Editor), allow control of:
  - System Events
  - Comet

Also ensure Comet is running and a tab title contains `Github Copilot`.

## 4) Files used by the automation (repo root)

- `scripts/comet_copilot_automation.applescript` — parameterized AppleScript (prompt, tab name, wait, webhook).
- `scripts/remote_copilot_trigger.sh` — copies the AppleScript to the Mac and invokes it via `osascript`.

## 5) Send a test prompt

```bash
REMOTE_HOST=100.84.184.37 \
REMOTE_USER=robert \
./scripts/remote_copilot_trigger.sh \
  "Ping from automation. Please reply with a short summary." \
  "Github Copilot" \
  40

# Pull Copilot’s response back into this repo
ssh robert@100.84.184.37 pbpaste > scripts/artifacts/copilot_response.txt
sed -n '1,40p' scripts/artifacts/copilot_response.txt
```

Optional: auto‑return via Slack webhook

```bash
REMOTE_HOST=100.84.184.37 \
REMOTE_USER=robert \
./scripts/remote_copilot_trigger.sh \
  "What kind of?" \
  "Github Copilot" \
  60 \
  "https://hooks.slack.com/services/XXX/YYY/ZZZ"
```

## 6) Troubleshooting

- `Permission denied (publickey,...)`: ensure the pubkey is appended to `~/.ssh/authorized_keys` on the Mac; permissions: `~/.ssh` 700, `authorized_keys` 600.
- `osascript is not allowed assistive access (-1719)`: grant Accessibility & Automation permissions as noted above.
- Tab not found: Comet must have a tab with title containing `Github Copilot`. The script falls back to cycling tabs with `⌘⌥→`.
- Response empty: Increase wait seconds (3rd arg) to allow Copilot to finish rendering.

## 7) Security & revocation

- Dedicated key only for this automation (`~/.ssh/id_ed25519_comet`).
- Revoke by removing its line from `~/.ssh/authorized_keys` on the Mac.
- No sudo required at any step.

