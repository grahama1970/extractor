# SANITY_MATRIX.md

This file catalogs **generic sanity scripts** (capability checks) that prove the environment/tooling can do the basics.

Sanity checks are **divorced from task correctness**:

- Sanity answers: “Can we do the basic operation at all?”
- Gates/tests answer: “Did we do the task correctly?”

## Rules (to avoid scope drift)

- Sanity checks cover **non-standard, failure-prone, project-specific capabilities** (external tools, auth, system deps).
- Do **NOT** add sanity checks for standard operations (reading/writing files, JSON parsing, sorting, basic Python).
- Keep the total sanity checks small (target 5–15).
- Each sanity check is one command/script, deterministic and fast.
- Prefer **local fixtures** committed in-repo (no network).
- Sanity scripts prove _capability_, not full correctness.
- Tasks reference sanity checks by **ID** (S1, S2, ...). Do not duplicate commands in task contracts.

## Semi-deterministic sanity checks (LLM/network)

Some sanity checks depend on external services (LLMs, network APIs, auth, rate limits). These are **semi-deterministic**:

- They can fail due to transient external conditions.
- They are still valuable to prove “the stack works” (auth/model/endpoint).
- They MUST NOT be used as hard gates in deterministic verifiers.

**Policy:**

- Semi-deterministic sanity checks run via `./preflight.sh` (or manually).
- Deterministic verifiers (`verify_task*.sh`) must remain deterministic and must not call semi-deterministic sanity scripts.

## Status conventions

- Exit `0` on pass
- Exit non-zero on fail (use clear stderr messages)
- Sanity scripts should not prompt for input

---

## S3: Camelot is installed and can extract at least one table from a fixture PDF

**Proves:** Camelot dependency is installed and functional in this environment.

**Command:**

```bash
bash sanity/S3_camelot_extract_fixture.sh
```

**Pass criteria:** exits 0 and prints `OK: S3_camelot_extract_fixture`.

**Notes:**

- This sanity check uses a fixture PDF in `fixtures/camelot_fixture.pdf`.
- If you don’t have Camelot installed, this will fail with install hints.

---

## S4: PDF -> table count pipeline (example capability)

**Proves:** a deterministic table counting command can be run end-to-end.

**Command:**

```bash
python3 tools/table_count.py fixtures/camelot_fixture.pdf
```

**Pass criteria:** prints a JSON object with `tables_found` integer and exits 0.

---

## Adding a new sanity check

When a “boring prerequisite” has bitten you twice (auth, missing tool, broken env), add:

- a new `sanity/S<N>_...` script
- an entry here
- and reference it by ID from task contracts and verifiers

---

## S5: SciLLM minimal call via Chutes (semi-deterministic)

**Proves:** SciLLM (or your LLM-calling wrapper) is configured and can complete a minimal request. **Strategy:** Start with a direct `curl` command to Chutes; if that works, try the SCILLM wrapper.

**Command:**

```bash
bash sanity/S5_scillm_min_call.sh
```

**Pass criteria:** exits 0 and prints `OK: S5_scillm_min_call`.

**Notes:**

- This sanity should be as deterministic as possible (small prompt, tight timeout).
- Prefer a local/stub endpoint in dev if available; otherwise mark it as “semi-deterministic” and keep it separate from deterministic gates.
- **Critical:** If the SciLLM Chutes call doesn't work (e.g. library issues), try using a direct `curl` command as a fallback.
  ```bash
  source .env
  curl -X POST https://llm.chutes.ai/v1/chat/completions \
    -H "Authorization: Bearer $CHUTES_API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "Qwen/Qwen3-VL-235B-A22B-Instruct",
      "messages": [
        {
          "role": "user",
          "content": [
            {"type": "text", "text": "Describe this image."},
            {
              "type": "image_url",
              "image_url": {
                "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
              }
            }
          ]
        }
      ],
      "stream": true,
      "max_tokens": 1024,
      "temperature": 0.7
    }'
  ```
