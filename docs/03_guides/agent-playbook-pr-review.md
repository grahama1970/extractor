# Agent Playbook: Copilot Review → Slack → Arango

This cheat sheet lets any project agent run the automated review loop end-to-end without human cleanup. Follow the steps in order.

---

## 1. Prepare the Branch

1. `git checkout -b <feature-branch>`
2. Make your changes and run `pytest -q` or project-specific checks.
3. `git status` should show only intentional edits.
4. Commit with a descriptive message (`git commit -am "feat: ..."`).
5. Push: `git push origin HEAD`.

## 2. Open a Draft PR (Auto-Context)

1. `gh pr create --base main --head <feature-branch> --title "..." --draft --fill`
2. Our pull-request template already injects the Copilot review brief (context, clarifying questions, files to inspect, diff request). Do **not** remove it.
3. Apply the `copilot-review` label:
   ```bash
   gh pr edit <number> --add-label copilot-review
   ```

## 3. Wait for Copilot Review

- Copilot is automatically requested on draft PRs when the label is present.
- When Copilot posts an **approved** review, the notifier workflow triggers.

## 4. What the Workflow Does (No Action Needed)

1. Sets `copilot/review` commit status on the PR head SHA.
2. Posts the acknowledgement comment: `✅ Copilot review processed ...`.
3. Removes the `copilot-review` label so the loop won’t repeat accidentally.
4. Logs a memory episode (`summary: "Copilot review processed"`) with PR, SHA, reviewer, timestamp.
5. Sends a Slack message via the Incoming Webhook secret.

## 5. Verify Outcomes (Optional but Recommended)

| Signal | Command | Expectation |
| --- | --- | --- |
| Slack | check `#incoming-webhook` | `:copilot:` message with repo/PR info |
| GitHub | PR checks tab | `copilot/review` status = success |
| Arango | ```python3 -m devops_agent.cli memory query --aql "FOR d IN devops_episodes FILTER d.summary == 'Copilot review processed' SORT d.ts DESC LIMIT 1 RETURN d"``` | Latest document matches PR |

## 6. Reset for Another Run (Smoke Testing)

1. Delete the acknowledgement comment:
   ```bash
   gh api repos/<owner>/<repo>/issues/comments/<commentID> -X DELETE
   ```
2. Re-apply `copilot-review` label to the PR.
3. Trigger the workflow manually if needed:
   ```bash
   gh workflow run copilot-review-notify.yml \
     --ref <feature-branch> \
     --field pr=<number> \
     --field sha=<current SHA> \
     --field state=approved \
     --field reviewer=github-copilot[bot]
   ```

## 7. Secrets & Config (Only Once per Repo)

| Secret | Purpose |
| --- | --- |
| `SLACK_WEBHOOK_URL` | Slack notification target |
| `TAILSCALE_AUTHKEY` (reusable) | Allows GitHub runner to reach Arango |
| `ARANGO_URL`, `ARANGO_DB`, `ARANGO_USER`, `ARANGO_PASS` | Memory episode writes |

Ensure `devops-agent.toml` points `[memory]` to the same endpoint so local CLI queries match CI writes.

## 8. Cleanup & Merge

1. After Copilot approves and tests pass, mark the PR “Ready for review” if you need a human pass.
2. Merge when policy allows (`copilot/review` is now a required status).
3. Delete the branch: `gh pr close <number> --delete-branch` (if merged) or `git push origin --delete <feature-branch>`.

Keep this playbook nearby so every agent follows the same frictionless loop.
