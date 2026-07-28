# Strategy Classifier Ready for Promotion

- **macro_f1**: 0.9963 (threshold: 0.85)
- **n_samples**: 24269 (threshold: 500)

To promote from shadow to active:
```bash
export STRATEGY_SELECTOR_MODE=active
```

Or update `/assistant` registry: set `shadow_mode: false`
