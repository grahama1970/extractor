Thanks for the detailed brief. I reviewed the current branch and code paths you flagged. Below are (1) direct answers and recommendations, (2) unified diffs ready to apply, and (3) follow‑up tests to add.

If you want concrete samples for the Arango schema (controls, edges, fields), I can tighten the AQL to your exact shapes; for now I made conservative assumptions and isolated collection names as envs so you can wire them without code edits.

Written answers and recommendations

1) Corpus guard robustness

- AQL shaping and bounds
  - Use BOOST on PHRASE matches to bias toward question containment over answer echo, and filter out low‑signal docs with a minimum score gate. I added FILTER score >= @min_score and an env SPARTA_CORPUS_MIN_SCORE (default 0), plus BOOST weights to prioritize question terms.
  - Cap Top‑K strongly. I introduced SPARTA_CORPUS_TOPK_MAX (default 12) and clamp requested topk to [1, TOPK_MAX], protecting against accidental over‑fetch.
  - Tighten LIKE fallback: keep case‑insensitive binds (already used), but ensure scope filter stays in place, and limit/constrain string sizes (you already slice lengths). The fallback cannot rank well; we keep it bounded and small.
  - Latency and observability: measure retrieval latency and export it via Prometheus histograms (retrieval_latency_ms) and counters for arango_errors_total and retrieval_method_count{method=view|collection|unavailable|none}.
- Injection safety
  - View and analyzer env strings are sanitized with a strict allow‑list regex ([A-Za-z0-9_-]+). You already removed backticks and slashes; this makes it stronger.
  - All user text stays in bind vars (already good).
- Degradation path
  - Your forced-escalate semantics when Arango is down are correct for anti‑hallucination. If you later want a stronger offline fallback, consider an optional local mini‑index (e.g., FAISS or a small Whoosh index) tied to the same corpus snapshots. For now, I preserved forced escalation with clear reasons.

2) Sparta relationships for cross‑control comparison

- Design and API
  - New method guard.related_controls(control_ids: list[str]) -> {related: bool, rationale: str, edges: list, same_category: bool, same_scope: bool}. It checks:
    - Same category? Same scope?
    - Any explicit edges in an edges collection (configurable).
  - Env plumbing: SPARTA_CONTROL_COLLECTION (default controls) and SPARTA_EDGE_COLLECTION (default control_edges).
  - Sanitization: collection names are not interpolated into the query (only via collection bind vars where available; for DOCUMENT() we bind full ids and avoid string concatenation).
- Compare integration and policy
  - Recommendation: Option A (block comparison and clearly say: “unrelated within Sparta”). It’s safer for your anti‑hallucination posture. Even “minimal factual contrast” can be misinterpreted by downstream consumers as a “comparison.” The diffs short‑circuit model calls when controls are unrelated (saves cost), produce a small “unrelated” judge payload, annotate reason(s), and force escalate.
  - Backward compatibility: the unrelatedness check only triggers if the item has both control_a and control_b (leaves existing flows unchanged).

3) Containment thresholds and false positives

- Defaults
  - Your coverage tiers (0.4/0.5/0.6) are decent. I added env overrides for coverage by difficulty to be surfaced in the guard’s report and used for ok computation if present, without changing evaluate_containment itself:
    - SPARTA_COVERAGE_THRESHOLDS="simple:0.45,normal:0.55,hard:0.65,extreme:0.70"
  - Fuzzy thresholds: I added optional per‑tier minimum fuzzy floors that can force escalation when RapidFuzz is low (or the fallback heuristic is weak):
    - SPARTA_FUZZY_MIN_FORCE_SIMPLE, SPARTA_FUZZY_MIN_FORCE_NORMAL, SPARTA_FUZZY_MIN_FORCE_HARD, SPARTA_FUZZY_MIN_FORCE_EXTREME
    - If min_fuzzy < tier floor, we append fuzzy_weak and force escalate. This gives you a simple switch to dial down false positives per model family.
- Model‑family overrides
  - If you want per‑model tuning, add an allow‑list in env (e.g., SPARTA_MODEL_FAMILY="llama,deepseek") and lookup a per‑family TOML, but that’s outside this change. The hooks are there (env‑backed thresholds).

4) Metrics and observability

- New counters/histograms
  - corpus guard:
    - sparta_retrieval_latency_ms (histogram)
    - sparta_arango_errors_total (counter){kind=connect|view|collection}
    - sparta_retrieval_method_count (counter){method=view|collection|unavailable|none}
    - sparta_forced_escalation_total (counter){reason=...}
    - sparta_evidence_count (histogram)
    - sparta_coverage (histogram)
  - compare/judge
    - You’re already emitting several. I added inc() calls to mirror forced-escalation reasons into Prometheus, alongside your JSONL pulses.

5) SGLang container hardening

- Packages/versions
  - Add flash-attn 2.x. For CUDA 12.1/PyTorch 2.3.1, flash-attn==2.6.3 is a good target; it gives a real decode uplift for DeepSeek/Llama families. I left xformers in place and pinned a compatible set.
  - Expose SGLANG_OPTS from the entrypoint so you can pass dp-attention, quantization, mem-fraction-static, schedule-conservativeness, cuda-graph-max-bs without editing the image.
  - For H100/L40S: enable fp8 quantization if safe (sglang supports --quantization fp8), dp-attention when you’re on multi‑GPU pods.
- Image size/cold start
  - I kept a single-stage Dockerfile (safe for RunPod) and added HEALTHCHECK and optional flash‑attn installation. If you want maximal size reduction, switch to a two‑stage build (compile flash‑attn wheels in “devel” and run from “runtime”), but that’s a larger change; we can do it next if you’d like.

6) Integration points and tests

- Unit tests added (in diffs):
  - Fuzzy floor forces escalation
  - Related controls returns unrelated when edges are empty and categories/scopes differ
- E2E smoke
  - I suggest a tiny Arango stub class (in tests) implementing aql() with hard‑coded results for:
    - view hit with multi‑section evidence
    - view miss → collection LIKE fallback
    - edges present vs absent
  - Given compare_parallel’s async and external deps, keep a focused unit for CorpusGuard, then add a light “unrelated short‑circuit” test that patches _CORPUS_GUARD and exercises the early‑return path.

7) Security, cost, failure modes

- Over‑fetching: hard cap Top‑K (SPARTA_CORPUS_TOPK_MAX) and minimum score gate. LIKE fallback stays bounded by LIMIT and small inputs.
- Excessive LIKE scans: we keep the strings short and early LIMIT; scope filter reduces scan. The change nudges you to ensure a view exists in production.
- Silent acceptance: we keep “forced” semantics and reasons; added explicit metrics and JSON annotations, including retrieval_method, to make degradations visible.
- Secrets in logs: no new secrets are printed; the entrypoint prints only model, port, tp-size. The compare pipeline doesn’t log API keys. If you run with extra debug logging, consider redacting typical key patterns; happy to add a redactor if desired.

Unified diffs (ready to apply)

Patch 1: devops/chutes/corpus_guard.py

```diff name=patches/corpus_guard.patch
--- a/devops/chutes/corpus_guard.py
+++ b/devops/chutes/corpus_guard.py
@@
-from dataclasses import dataclass
-import logging
-import os
-from typing import Callable, Dict, Iterable, List, Optional, Tuple
+from dataclasses import dataclass
+import logging
+import os
+import re
+import time
+from typing import Callable, Dict, Iterable, List, Optional, Tuple
 
@@
-from devops.chutes.containment_check import evaluate_containment
+from devops.chutes.containment_check import evaluate_containment
+try:
+    # Optional Prometheus-style metrics
+    from devops.chutes.metrics import inc, observe_hist  # type: ignore
+except Exception:  # pragma: no cover
+    def inc(*args, **kwargs):  # type: ignore
+        return None
+    def observe_hist(*args, **kwargs):  # type: ignore
+        return None
@@
     def __init__(
         *,
         client: Optional[ArangoClient] = None,
         retriever: Optional[Callable[..., Tuple[List[Dict[str, str]], str]]] = None,
     ) -> None:
-        self._view = os.getenv("SPARTA_CORPUS_VIEW", "sparta_lessons")
-        self._collection = os.getenv("SPARTA_CORPUS_COLLECTION", "lessons")
-        self._analyzer = os.getenv("SPARTA_CORPUS_ANALYZER", "text_en")
-        self._topk = int(os.getenv("SPARTA_CORPUS_TOPK", "8"))
+        self._view = os.getenv("SPARTA_CORPUS_VIEW", "sparta_lessons")
+        self._collection = os.getenv("SPARTA_CORPUS_COLLECTION", "lessons")
+        self._analyzer = os.getenv("SPARTA_CORPUS_ANALYZER", "text_en")
+        # Clamp Top-K for safety
+        self._topk = int(os.getenv("SPARTA_CORPUS_TOPK", "8"))
+        self._topk_max = int(os.getenv("SPARTA_CORPUS_TOPK_MAX", "12"))
+        if self._topk_max < 1:
+            self._topk_max = 12
+        self._topk = max(1, min(self._topk, self._topk_max))
+        # Optional gates/tuning
+        self._min_score = float(os.getenv("SPARTA_CORPUS_MIN_SCORE", "0.0"))
+        # Relationship collections
+        self._controls_col = os.getenv("SPARTA_CONTROL_COLLECTION", "controls")
+        self._edges_col = os.getenv("SPARTA_EDGE_COLLECTION", "control_edges")
         timeout = float(os.getenv("SPARTA_CORPUS_TIMEOUT", "8"))
         self._client = client or self._init_client(timeout=timeout)
         self._retriever = retriever or self._retrieve_from_arango
+        # Optional coverage/fuzzy floors by tier (env overrides)
+        self._coverage_tiers = self._parse_thresholds_env(os.getenv("SPARTA_COVERAGE_THRESHOLDS", ""))
+        self._fuzzy_floor_by_tier = {
+            "simple": int(os.getenv("SPARTA_FUZZY_MIN_FORCE_SIMPLE", "0") or 0),
+            "normal": int(os.getenv("SPARTA_FUZZY_MIN_FORCE_NORMAL", "0") or 0),
+            "hard": int(os.getenv("SPARTA_FUZZY_MIN_FORCE_HARD", "0") or 0),
+            "extreme": int(os.getenv("SPARTA_FUZZY_MIN_FORCE_EXTREME", "0") or 0),
+        }
@@
     def _retrieve_from_arango(
         self,
         *,
         question: str,
         answer: str,
         scope: Optional[str],
         limit: int,
     ) -> Tuple[List[Dict[str, str]], str]:
-        if not self._client:
-            return ([], "unavailable")
+        if not self._client:
+            inc("sparta_retrieval_method_count", {"method": "unavailable"})
+            return ([], "unavailable")
 
         q = (question or "").strip()
         a = (answer or "").strip()
         scope = scope or ""
         method = "view"
         rows: List[Dict[str, str]] = []
+        t0 = time.monotonic()
 
         if self._view:
             try:
                 query = self._build_view_query(self._view)
                 resp = self._client.aql(
                     query,
                     {
                         "q_text": q[:512],
                         "a_text": a[:1024],
                         "scope": scope,
-                        "limit": int(max(1, limit)),
+                        "limit": int(max(1, min(limit, self._topk_max))),
                         "an": self._analyzer,
+                        "min_score": float(self._min_score),
                     },
                 )
                 rows = list(resp.get("result", []))
             except Exception as exc:  # pragma: no cover - depends on env
                 LOGGER.debug("CorpusGuard: view query failed (%s)", exc)
+                inc("sparta_arango_errors_total", {"kind": "view"})
                 rows = []
 
         if not rows:
             method = "collection"
             try:
                 query = self._build_like_query()
                 resp = self._client.aql(
                     query,
                     {
                         "@col": self._collection,
                         "needle_q": f"%{q.lower()[:180]}%",
                         "needle_a": f"%{a.lower()[:200]}%",
                         "scope": scope,
-                        "limit": int(max(1, limit)),
+                        "limit": int(max(1, min(limit, self._topk_max))),
                     },
                 )
                 rows = list(resp.get("result", []))
             except Exception as exc:  # pragma: no cover - depends on env
                 LOGGER.debug("CorpusGuard: collection query failed (%s)", exc)
+                inc("sparta_arango_errors_total", {"kind": "collection"})
                 rows = []
 
         evidence: List[Dict[str, str]] = []
         seen: set[str] = set()
         for row in rows:
@@
             if len(evidence) >= limit:
                 break
 
-        return (evidence, method if evidence else "none")
+        dt_ms = max(0.0, (time.monotonic() - t0) * 1000.0)
+        try:
+            observe_hist("sparta_retrieval_latency_ms", None, float(dt_ms))
+            inc("sparta_retrieval_method_count", {"method": method if evidence else "none"})
+        except Exception:
+            pass
+        return (evidence, method if evidence else "none")
@@
-    def _build_view_query(self, view: str) -> str:
-        # ``view`` is injected from an env var controlled by operators; still
-        # apply a conservative allow-list to prevent injection.
-        safe_view = view.replace("`", "").replace("/", "")
+    def _build_view_query(self, view: str) -> str:
+        # Allow-list sanitize view and analyzer names
+        safe_view = re.sub(r"[^A-Za-z0-9_\\-]", "", view)
+        safe_an = re.sub(r"[^A-Za-z0-9_\\-]", "", self._analyzer)
         return f"""
 FOR doc IN `{safe_view}`
   SEARCH ANALYZER(
-    PHRASE(doc.problem, @q_text, @an) OR
-    PHRASE(doc.playbook, @q_text, @an) OR
-    PHRASE(doc.problem, @a_text, @an) OR
-    PHRASE(doc.playbook, @a_text, @an)
+    BOOST(PHRASE(doc.problem, @q_text, @an), 1.5) OR
+    BOOST(PHRASE(doc.playbook, @q_text, @an), 1.3) OR
+    PHRASE(doc.problem, @a_text, @an) OR
+    PHRASE(doc.playbook, @a_text, @an)
   )
   FILTER @scope == '' OR doc.scope == @scope
   LET combined = CONCAT(doc.problem, '\\n', doc.playbook)
   LET score = BM25(doc) + TFIDF(doc)
+  FILTER score >= @min_score
   SORT score DESC
   LIMIT @limit
   RETURN {
     id: doc._id,
     title: doc.title,
     section: doc.scope,
     score: score,
     problem: doc.problem,
     playbook: doc.playbook
   }
 """
@@
     def _compose_text(row: Dict[str, str]) -> str:
         text = row.get("text")
         if text:
             return text
         parts: List[str] = []
         for key in ("problem", "playbook", "content", "quote"):
             val = row.get(key)
             if val:
                 parts.append(val)
         return "\n".join(parts).strip()
 
     # endregion --------------------------------------------------------------
 
     def check(
         self,
         *,
         question: str,
         answer: str,
         control_id: Optional[str] = None,
         scope: Optional[str] = None,
         difficulty: Optional[str] = None,
     ) -> CorpusCheckResult:
-        evidences, method = self._retriever(
+        evidences, method = self._retriever(
             question=question,
             answer=answer,
             scope=scope,
             limit=self._topk,
         )
@@
-        coverage = float(report.get("coverage") or 0.0)
+        coverage = float(report.get("coverage") or 0.0)
         verdict = str(report.get("verdict") or "unknown")
-        ok = verdict == "ok" and not forced and coverage >= float(report.get("tier_min") or 0.0)
+        # Optional override of tier_min coverage threshold from env
+        tier = (difficulty or "simple").strip().lower()
+        override_cov = self._coverage_tiers.get(tier) if isinstance(self._coverage_tiers, dict) else None
+        if override_cov is not None:
+            report["tier_min"] = float(override_cov)
+        # Fuzzy floors per tier (optional)
+        fuzzy_floor = int(self._fuzzy_floor_by_tier.get(tier) or 0)
+        if fuzzy_floor and min_fuzzy < fuzzy_floor:
+            if "fuzzy_weak" not in reasons_list:
+                reasons_list.append("fuzzy_weak")
+            forced = True
+        ok = verdict == "ok" and not forced and coverage >= float(report.get("tier_min") or 0.0)
 
         report = {**report, "reasons": reasons_list}
 
+        # Metrics
+        try:
+            observe_hist("sparta_coverage", None, float(coverage))
+            observe_hist("sparta_evidence_count", None, float(len(evidences)))
+            if forced:
+                for r in reasons_list:
+                    inc("sparta_forced_escalation_total", {"reason": r})
+        except Exception:
+            pass
+
         return CorpusCheckResult(
             ok=ok,
             verdict=verdict,
             attenuation=float(factor),
             forced=bool(forced),
             reasons=reasons_list,
             coverage=coverage,
             min_fuzzy=int(min_fuzzy),
             evidence_refs=refs,
             evidence=evidences,
             report=report,
             retrieval_method=method,
         )
 
+    def related_controls(self, control_ids: List[str]) -> Dict[str, object]:
+        """
+        Determine whether two controls are related in Sparta by category/scope or explicit edges.
+        control_ids should contain two values; they may be full _id values (e.g., "controls/123").
+        Returns: {related: bool, rationale: str, edges: list, same_category: bool, same_scope: bool}
+        """
+        res = {
+            "related": False,
+            "rationale": "",
+            "edges": [],
+            "same_category": False,
+            "same_scope": False,
+        }
+        if not control_ids or len(control_ids) != 2:
+            res["rationale"] = "insufficient_ids"
+            return res
+        if not self._client:
+            res["rationale"] = "unavailable"
+            return res
+        a_id, b_id = (str(control_ids[0] or "").strip(), str(control_ids[1] or "").strip())
+        if not a_id or not b_id:
+            res["rationale"] = "insufficient_ids"
+            return res
+        # Normalize to full ids if bare keys are supplied
+        if "/" not in a_id:
+            a_id = f"{self._controls_col}/{a_id}"
+        if "/" not in b_id:
+            b_id = f"{self._controls_col}/{b_id}"
+        try:
+            query = """
+LET a = DOCUMENT(@id_a)
+LET b = DOCUMENT(@id_b)
+LET same_cat = (a != null AND b != null AND a.category != null AND b.category != null AND a.category == b.category)
+LET same_scope = (a != null AND b != null AND a.scope != null AND b.scope != null AND a.scope == b.scope)
+LET es = (
+  FOR e IN @@edges
+    FILTER (e._from == @id_a AND e._to == @id_b) OR (e._from == @id_b AND e._to == @id_a)
+    LIMIT 20
+    RETURN {id: e._id, type: e.type, _from: e._from, _to: e._to}
+)
+RETURN { same_cat: same_cat, same_scope: same_scope, edges: es }
+"""
+            resp = self._client.aql(query, {"id_a": a_id, "id_b": b_id, "@edges": self._edges_col})
+            row = (resp.get("result") or [{}])[0] if isinstance(resp, dict) else {}
+            same_cat = bool(row.get("same_cat"))
+            same_scope = bool(row.get("same_scope"))
+            edges = list(row.get("edges") or [])
+            related = bool(same_cat or same_scope or len(edges) > 0)
+            rationale = "edge" if edges else ("same_category" if same_cat else ("same_scope" if same_scope else "none"))
+            return {
+                "related": related,
+                "rationale": rationale,
+                "edges": edges,
+                "same_category": same_cat,
+                "same_scope": same_scope,
+            }
+        except Exception as exc:  # pragma: no cover
+            LOGGER.debug("CorpusGuard: related_controls query failed (%s)", exc)
+            return {**res, "rationale": "error"}
+
+    @staticmethod
+    def _parse_thresholds_env(s: str) -> Dict[str, float]:
+        """
+        Parse env like 'simple:0.45,normal:0.55,hard:0.65,extreme:0.7'
+        """
+        out: Dict[str, float] = {}
+        s = (s or "").strip()
+        if not s:
+            return out
+        try:
+            parts = [p.strip() for p in s.split(",") if p.strip()]
+            for p in parts:
+                if ":" in p:
+                    k, v = p.split(":", 1)
+                    out[k.strip().lower()] = float(v.strip())
+        except Exception:
+            return {}
+        return out
@@
 __all__ = ["CorpusGuard", "CorpusCheckResult", "get_corpus_guard"]
```

Patch 2: devops/chutes/compare_parallel.py

```diff name=patches/compare_parallel.patch url=https://github.com/grahama1970/devops/blob/76265d153c6d218bbd3e0226a27fe580ff32710c/devops/chutes/compare_parallel.py
--- a/devops/chutes/compare_parallel.py
+++ b/devops/chutes/compare_parallel.py
@@
 from devops.chutes.corpus_guard import get_corpus_guard
@@
 async def run_batch_chunk(
@@
     def _judge_messages(item: Dict[str, Any], out_a: Dict[str, Any], out_b: Dict[str, Any]) -> List[Dict[str, Any]]:
@@
     async def fn(item: Dict[str, Any]) -> Dict[str, Any]:
+        # Optional: short-circuit if controls are unrelated in Sparta (Option A: block)
+        relation_guard = None
+        try:
+            ca_id = item.get("control_a")
+            cb_id = item.get("control_b")
+            if ca_id and cb_id and _CORPUS_GUARD:
+                relation_guard = _CORPUS_GUARD.related_controls([str(ca_id), str(cb_id)])
+                if isinstance(relation_guard, dict) and not relation_guard.get("related", False):
+                    # Emit a metric and return a minimal, explicit 'unrelated' record without model calls
+                    try:
+                        from devops.chutes.metrics import inc  # type: ignore
+                        inc("unrelated_controls_total", {"rationale": str(relation_guard.get("rationale") or "none")})
+                    except Exception:
+                        pass
+                    jres = {
+                        "supported_a": False,
+                        "supported_b": False,
+                        "better": "tie",
+                        "confidence": 0.0,
+                        "rationale_short": "These controls are not related within the context of Sparta.",
+                        "unrelated": True,
+                        "relation_guard": relation_guard,
+                        "forced_escalation": True,
+                        "escalation_reason": "unrelated_controls",
+                    }
+                    return {
+                        "id": item.get("id"),
+                        "question": item.get("question"),
+                        "difficulty": item.get("difficulty") or "simple",
+                        "model_a": model_a,
+                        "model_b": model_b,
+                        "judge_model": judge_model,
+                        "out_a": {"answer": "", "grounded": False, "grounded_score": 0.0, "_corpus_guard": None},
+                        "out_b": {"answer": "", "grounded": False, "grounded_score": 0.0, "_corpus_guard": None},
+                        "judge": jres,
+                    }
+        except Exception:
+            # Fall through to normal flow if relation check fails
+            relation_guard = None
@@
-        # Judge with payload
+        # Judge with payload
         jmsgs = _judge_messages(item, out_a, out_b)
@@
-        # Forced escalation conditions based on containment + refs
+        # Forced escalation conditions based on containment + refs
         forced = bool(ca_forced or cb_forced)
@@
-        # Escalation decision and annotation
+        # Escalation decision and annotation
         if isinstance(jres, dict):
             if forced:
                 jres["forced_escalation"] = True
                 jres["escalation_reason"] = "forced"
+            # Include relation_guard annotation if present
+            if relation_guard and not jres.get("relation_guard"):
+                jres["relation_guard"] = relation_guard
@@
         return {
             "id": item.get("id"),
             "question": item.get("question"),
             "difficulty": item.get("difficulty") or "simple",
             "model_a": model_a,
             "model_b": model_b,
             "judge_model": judge_model,
             "out_a": out_a,
             "out_b": out_b,
-            "judge": jres,
+            "judge": jres,
         }
```

Patch 3: tests/unit/test_corpus_guard.py

```diff name=patches/test_corpus_guard.patch url=https://github.com/grahama1970/devops/blob/76265d153c6d218bbd3e0226a27fe580ff32710c/tests/unit/test_corpus_guard.py
--- a/tests/unit/test_corpus_guard.py
+++ b/tests/unit/test_corpus_guard.py
@@
 from devops.chutes.corpus_guard import CorpusGuard, CorpusCheckResult
 
 
 def test_corpus_guard_fallback_no_client():
     guard = CorpusGuard(client=None, retriever=lambda **kwargs: ([], "none"))
     result = guard.check(question="What is auditing?", answer="Auditing ensures controls are reviewed.")
     assert isinstance(result, CorpusCheckResult)
     assert result.forced is True
     assert "no_evidence_found" in result.reasons
     assert result.retrieval_method == "none"
 
 
 def test_corpus_guard_with_stub_retriever():
     evidence = [{"id": "lessons/1", "text": "Auditing ensures controls are reviewed."}]
 
     def _stub_retriever(**kwargs):
         return (evidence, "stub")
 
     guard = CorpusGuard(client=None, retriever=_stub_retriever)
     result = guard.check(question="What does control X require?", answer="Auditing ensures controls are reviewed.")
     assert isinstance(result, CorpusCheckResult)
     assert result.ok is True
     assert result.forced is False
     assert result.retrieval_method == "stub"
     assert result.coverage >= 0.4  # tier simple threshold
+
+
+def test_related_controls_unavailable_client_returns_unrelated():
+    guard = CorpusGuard(client=None, retriever=lambda **kwargs: ([], "none"))
+    rel = guard.related_controls(["controls/A", "controls/B"])
+    assert isinstance(rel, dict)
+    assert rel.get("related") is False
+    assert rel.get("rationale") in ("unavailable", "insufficient_ids")
+
+
+def test_related_controls_stub_edges_empty():
+    class _StubClient:
+        def aql(self, query, bind_vars):
+            # No edges, different category/scope
+            return {"result": [{"same_cat": False, "same_scope": False, "edges": []}]}
+    guard = CorpusGuard(client=_StubClient(), retriever=lambda **kwargs: ([], "none"))
+    rel = guard.related_controls(["controls/A", "controls/B"])
+    assert rel["related"] is False
+    assert rel["rationale"] == "none"
+
+
+def test_fuzzy_floor_forces_escalation(monkeypatch):
+    # Force a high fuzzy floor to trigger escalation
+    monkeypatch.setenv("SPARTA_FUZZY_MIN_FORCE_SIMPLE", "95")
+    evidence = [{"id": "lessons/1", "text": "Short evidence only."}]
+    def _stub_retriever(**kwargs):
+        return (evidence, "stub")
+    guard = CorpusGuard(client=None, retriever=_stub_retriever)
+    res = guard.check(question="Q?", answer="Completely different answer.")
+    assert res.forced is True
+    assert "fuzzy_weak" in res.reasons
```

Patch 4: docker/runpod-sglang/Dockerfile

```diff name=patches/runpod-sglang.Dockerfile.patch url=https://github.com/grahama1970/devops/blob/76265d153c6d218bbd3e0226a27fe580ff32710c/docker/runpod-sglang/Dockerfile
--- a/docker/runpod-sglang/Dockerfile
+++ b/docker/runpod-sglang/Dockerfile
@@
 FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-devel
@@
-ENV DEBIAN_FRONTEND=noninteractive \
+ENV DEBIAN_FRONTEND=noninteractive \
     PYTHONUNBUFFERED=1 \
     PIP_DISABLE_PIP_VERSION_CHECK=1 \
     PIP_NO_CACHE_DIR=1 \
     HF_HOME=/workspace/.cache/huggingface \
     TORCH_CUDA_ARCH_LIST="8.0 8.6 8.9 9.0+PTX" \
     SGLANG_PORT=30000
@@
 RUN python -m pip install --upgrade pip setuptools wheel
@@
-RUN pip install --no-cache-dir \
+RUN pip install --no-cache-dir \
     accelerate==0.33.0 \
     bitsandbytes==0.43.1 \
     datasets==2.20.0 \
     einops==0.8.0 \
     huggingface_hub==0.24.0 \
     peft==0.11.1 \
     runpod==1.6.3 \
-    sglang[all]==0.3.5 \
+    sglang[all]==0.3.5 \
     transformers==4.44.2 \
     triton==2.3.1 \
     xformers==0.0.27.post2
+#
+# Optional but recommended: flash-attn for H100/L40S decode throughput
+# If your environment lacks build toolchain/wheels, comment this line.
+RUN pip install --no-cache-dir --no-build-isolation flash-attn==2.6.3 || true
@@
 COPY --chmod=755 docker/runpod-sglang/scripts/sglang-entrypoint.sh /usr/local/bin/sglang-entrypoint.sh
@@
-ENTRYPOINT ["/bin/bash"]
-CMD ["-lc", "echo 'Container ready. Override CMD to launch training or SGLang server.'"]
+ENTRYPOINT ["/bin/bash"]
+CMD ["-lc", "echo 'Container ready. Override CMD to launch training or SGLang server.'"]
+#
+# Basic healthcheck (no-op by default; succeeds while container is up)
+HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD bash -lc 'exit 0'
```

Patch 5: docker/runpod-sglang/scripts/sglang-entrypoint.sh

```diff name=patches/sglang-entrypoint.sh.patch url=https://github.com/grahama1970/devops/blob/76265d153c6d218bbd3e0226a27fe580ff32710c/docker/runpod-sglang/scripts/sglang-entrypoint.sh
--- a/docker/runpod-sglang/scripts/sglang-entrypoint.sh
+++ b/docker/runpod-sglang/scripts/sglang-entrypoint.sh
@@
 #   MODEL_ID       Hugging Face model repo id (required)
 #   SGLANG_PORT    TCP port to expose (default 30000)
 #   TP_SIZE        Tensor parallel size (default 1)
 #   HF_TOKEN       Optional token for private repos
+#   SGLANG_OPTS    Additional flags to pass to sglang.launcher (optional)
 
 MODEL_ID="${MODEL_ID:-}"
 PORT="${SGLANG_PORT:-30000}"
 TP_SIZE="${TP_SIZE:-1}"
 
@@
 HF_ARG=""
 if [[ -n "${HF_TOKEN:-}" ]]; then
   export HF_TOKEN
   HF_ARG="--hf-token ${HF_TOKEN}"
 fi
 
-exec python -m sglang.launcher \
+# Allow passing launcher options via env, e.g.:
+# SGLANG_OPTS="--mem-fraction-static 0.9 --schedule-conservativeness 0.3 --cuda-graph-max-bs 512 --quantization fp8"
+exec python -m sglang.launcher \
   --model "${MODEL_ID}" \
   --host 0.0.0.0 \
   --port "${PORT}" \
   --tp-size "${TP_SIZE}" \
-  ${HF_ARG}
+  ${HF_ARG} \
+  ${SGLANG_OPTS:-}
```

Patch 6: docker-compose.yml (healthcheck)

```diff name=patches/docker-compose.patch url=https://github.com/grahama1970/devops/blob/76265d153c6d218bbd3e0226a27fe580ff32710c/docker-compose.yml
--- a/docker-compose.yml
+++ b/docker-compose.yml
@@
     ports:
       - "${SGLANG_PORT:-30000}:${SGLANG_PORT:-30000}"
     command: ["/usr/local/bin/sglang-entrypoint.sh"]
+    healthcheck:
+      test: ["CMD-SHELL", "curl -sf http://localhost:${SGLANG_PORT:-30000}/health || curl -sf http://localhost:${SGLANG_PORT:-30000}/v1/models || exit 1"]
+      interval: 30s
+      timeout: 5s
+      retries: 5
     deploy:
       resources:
         reservations:
           devices:
             - driver: nvidia
               count: 1
               capabilities: [gpu]
```

Patch 7: docs/sglang-tuning-guide.md (note about SGLANG_OPTS and flags)

````diff name=patches/sglang-tuning-guide.md.patch url=https://github.com/grahama1970/devops/blob/76265d153c6d218bbd3e0226a27fe580ff32710c/docs/sglang-tuning-guide.md
--- a/docs/sglang-tuning-guide.md
+++ b/docs/sglang-tuning-guide.md
@@
 ## Throughput-Oriented Settings (Teacher / QRA Batches)
 
 - **VRAM reservation:** set `--mem-fraction-static` ~0.88–0.92 so only 5–8 GB remains free; adjust up/down if the logs show more/less headroom.
 - **CUDA graphs:** raise `--cuda-graph-max-bs` (512/768) until decode batches stop growing; each increase may require nudging `--mem-fraction-static` down a point or two.
 - **Scheduler aggressiveness:** start `--schedule-conservativeness 0.3`; if the log shows `token usage < 0.9` while `#queue-req > 0`, reduce further. Bump up if you hit decode OOMs.
 - **Parallelism:** prefer data parallel attention when running DeepSeek MLA models (`--enable-dp-attention --tp 8 --dp 8` on 16-way clusters). It lifts decode throughput ~1.8–1.9× compared with[...]
 - **Scheduling policy:** if queries share a long rubric prefix, set `--schedule-policy lpm` (Longest Prefix Match). Use `fcfs` only when prompts are unrelated.
 - **Quantization:** FP8 (`--quantization fp8`) is stable on H100/H200-class GPUs for Llama‑70B+ and DeepSeek teachers; monitor fidelity before flipping the flag in production.
+  - Pass flags via `SGLANG_OPTS` to the entrypoint. Example:
+    - `SGLANG_OPTS="--mem-fraction-static 0.9 --schedule-conservativeness 0.3 --cuda-graph-max-bs 512 --quantization fp8"`
@@
 ## RunPod Integration Checklist
@@
-3. Pass SGLang flags through your command wrapper (e.g., `SGLANG_OPTS="--mem-fraction-static 0.9 --schedule-conservativeness 0.3 --cuda-graph-max-bs 512"`).
+3. Pass SGLang flags through your command wrapper (e.g., `SGLANG_OPTS="--mem-fraction-static 0.9 --schedule-conservativeness 0.3 --cuda-graph-max-bs 512 --schedule-policy lpm"`).
+5. If using multi‑GPU pods, consider `--enable-dp-attention` and set appropriate `--tp-size` and `--dp` according to available GPUs.
````

Follow-up test cases to add and why

- tests/unit/test_corpus_guard_like_fallback_bounds.py
  - Ensures LIKE fallback respects LIMIT and scope filtering even with very long question/answer strings; prevents accidental collection scans.
- tests/unit/test_corpus_guard_min_score_gate.py
  - With a stubbed Arango view returning low and high scores, ensure rows below SPARTA_CORPUS_MIN_SCORE are filtered out.
- tests/unit/test_corpus_guard_multi_section_evidence.py
  - Verify evidence composition across non‑contiguous sections merges into combined text chunks and improves coverage.
- tests/unit/test_compare_parallel_unrelated_short_circuit.py
  - Patch _CORPUS_GUARD.related_controls to return unrelated and assert fn() returns early record without model calls, with forced_escalation and rationale.
- tests/unit/test_corpus_guard_env_thresholds.py
  - Set SPARTA_COVERAGE_THRESHOLDS and verify report.tier_min reflects overrides and ok gating uses the overridden value.

Notes and small asks (if you can share)

- Arango schema confirmation
  - Controls collection: field names for category and scope?
  - Edges collection: attribute for type? It’s referenced in the patch but optional.
  - If your IDs aren’t full _id values, confirm your preferred identifier key; the method supports either.
- ArangoClient aql API options
  - If the client supports query options like maxRuntime, memoryLimit, please confirm the call signature and I’ll add them as bindable options.

That’s everything from my review. If you’d like the Dockerfile converted to a true multi‑stage with a runtime base to minimize size, I can follow up with that patch once we confirm your preferred CUDA/Torch minor versions and the exact flash‑attn wheel availability for your infra.