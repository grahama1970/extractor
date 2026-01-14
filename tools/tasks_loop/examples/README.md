# tasks_loop Examples

This directory contains illustrative examples of the tasks_loop pattern.

## contacts_cli Example

A simple example showing the gate pattern with a contacts normalization task.

### Files

| File                         | Purpose                             |
| ---------------------------- | ----------------------------------- |
| `contacts_cli.py`            | Simple CLI that normalizes contacts |
| `sample_contacts.jsonl`      | Input test data                     |
| `expected_contacts.json`     | Expected output                     |
| `gate_contacts_cli.py`       | Gate that verifies the CLI          |
| `gate_normalize_contacts.py` | Gate for normalize function         |

### Running the Example

```bash
# Run the CLI
python tools/tasks_loop/examples/contacts_cli.py \
  --input tools/tasks_loop/examples/sample_contacts.jsonl \
  --output /tmp/normalized.json

# Run the gate
python tools/tasks_loop/examples/gate_contacts_cli.py
```

### How It Demonstrates tasks_loop

1. `contacts_cli.py` - A pipeline step (like `s05_table_extractor.py`)
2. `gate_contacts_cli.py` - A verify script that:
   - Runs the CLI
   - Checks output exists
   - Validates output matches expected
   - Returns exit 0 (PASS), 1 (FAIL), or 42 (CLARIFY)
