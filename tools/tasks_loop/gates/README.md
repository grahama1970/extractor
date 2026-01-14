# Gates & Contracts

This directory contains the **Gates** for the `tasks_loop` pipeline.

## 🧠 The Philosophy

In the `tasks_loop` verification system, **Gates are generic, but Contracts are specific.**

- **Gates** (`gate_sXX.py`): Static Python scripts that define _how_ to measure success (e.g., "Check if the table count matches expectations"). They are code.
- **Contracts** (`contracts/*.json`): Data files that define _what_ success looks like for a specific fixture (e.g., "Expect 6 tables"). They are data.

## 🔄 The Flow

1.  **Define Expectations**: You write a `SPEC.md` for your fixture (e.g., `fixtures/BHT_CV32A65X_test/SPEC.md`).
2.  **Compile Contracts**: The `utils/compile_contracts.py` script reads the `SPEC.md` and generates JSON contract files.
    ```bash
    python tools/tasks_loop/utils/compile_contracts.py --fixture BHT_CV32A65X_test
    # ↳ fixtures/BHT_CV32A65X_test/contracts/s05.json
    ```
3.  **Run Gate**: The Gate script reads the _Contract_ and compares it to the _Pipeline Output_.
    ```bash
    # Internally calls load_contract("BHT_CV32A65X_test") -> reads contracts/s05.json
    python tools/tasks_loop/gates/gate_s05.py --fixture BHT_CV32A65X_test
    ```

## 🛠️ Usage

Gates are typically run automatically by `run_pipeline.py`, but you can run them manually for debugging:

```bash
# Debug why Step 04 failed
python tools/tasks_loop/gates/gate_s04.py --fixture BHT_Mutant_Eq
```

## 📂 Directory Structure

- `gate_sXX.py`: The verifier script for Step XX.
- `gate_utils.py`: (in parent dir) Helpers for loading JSON and printing GHA-style errors.
