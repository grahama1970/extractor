import importlib
import os
import dotenv


def test_env_default_model_chain(monkeypatch):
    # Ensure LITELLM_MODEL is not set, prefer DEFAULT_LITELLM_MODEL in our code
    monkeypatch.delenv("LITELLM_MODEL", raising=False)
    monkeypatch.delenv("LITELLM_DEFAULT_MODEL", raising=False)
    monkeypatch.setenv("DEFAULT_LITELLM_MODEL", "openai/gpt-4o-mini")
    monkeypatch.delenv("OLLAMA_DEFAULT_MODEL", raising=False)

    # Prevent .env reload from overriding our env in the module under test
    monkeypatch.setattr(dotenv, "find_dotenv", lambda *a, **k: "")
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)

    # Verify environment preconditions for the chain
    assert os.getenv("LITELLM_MODEL") is None
    assert os.getenv("LITELLM_DEFAULT_MODEL") is None
    assert os.getenv("DEFAULT_LITELLM_MODEL") == "openai/gpt-4o-mini"
    assert os.getenv("OLLAMA_DEFAULT_MODEL") is None

    import extractor.pipeline.utils.litellm_call as lc

    importlib.reload(lc)
    assert lc.MODEL == "openai/gpt-4o-mini"
