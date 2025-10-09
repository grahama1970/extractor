Using local SciLLM fork in extractor

Install options
- Editable (reflects live changes):
  - `uv pip install -e /home/graham/workspace/experiments/litellm`
- Project extras (preferred):
  - `uv pip install -e ".[llm,scillm-local]"`

Runtime imports
- Code continues to import `litellm`:
  - `from litellm import completion`

Checks
- `python -c "import litellm,inspect; print(litellm.__file__)"`
- `python -c "import importlib.metadata as m; print([d.metadata['Name'] for d in m.distributions() if d.metadata['Name'].lower() in ('scillm','litellm')])"`

CI/VCS alternative
- Use a Git URL instead of a file path:
  - `scillm @ git+ssh://github.com/<you>/litellm.git@<branch-or-commit>`

