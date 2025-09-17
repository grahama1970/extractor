# Gamified Instance Prompt — codex_01 / raise-the-plasma-core-density-while-maintaining-confinement-quality-by-injecting-fuel-pellets-or-modulating-fueling-rates-at-the-plasma-edge-without-triggering-disruptions

## Original Prompt
```markdown
The three amended approaches to increase the efficiency of a tokamak reactor, now including their corresponding mathematical or algorithmic methods for testing and verification, are:

1. **Increasing Plasma Density with Controlled Fueling**  
   Approach: Raise the plasma core density while maintaining confinement quality by injecting fuel pellets or modulating fueling rates at the plasma edge without triggering disruptions.  
   Mathematical Method: Model plasma density and temperature evolution using coupled nonlinear drift-diffusion partial differential equations (PDEs) representing particle transport in the plasma. Use model predictive control (MPC) to solve optimal control programs constrained by safety limits (e.g., edge density threshold). Verification involves solving mixed-integer quadratic programming (MIQP) problems for real-time control strategies, simulating how fueling impact efficiency and confinement.[1]

2. **Magnetic and Wave Pattern Control to Suppress Edge Instabilities**  
   Approach: Apply complex magnetic field configurations or wave patterns near the plasma edge to suppress disruptive instabilities such as Edge Localized Modes (ELMs). This stabilizes the plasma surface, allowing longer, more stable operation phases.  
   Mathematical Method: Employ free-boundary equilibrium modeling via the Grad–Shafranov equation coupled with magnetohydrodynamic (MHD) stability theory. The plasma and conductor dynamics can be simulated with circuit models and polynomial-parametrized plasma profiles constrained by plasma current, plasma pressure (β), and safety factor (q). Control policies can be optimized via reinforcement learning algorithms acting within these simulators to test stability improvements quantitatively.[3]

3. **Optimized Heat Management and Extraction**  
   Approach: Design adaptive heat removal systems integrated with plasma boundary control to maximize energy extraction while keeping plasma stable and preventing material damage.  
   Mathematical Method: Use integrated multi-physics simulations combining heat transport equations, plasma turbulence models, and boundary layer dynamics. Predictive models with reduced-order neural networks or parameterized transport solvers can help design and test coolant flow and plasma-facing component configurations. Performance verification is done by simulating heat flux loads and their influence on plasma edge stability, iterating for optimal design.[2][8]

These approaches combine physics-based differential equation modeling, constrained optimal control techniques, and AI-enhanced learning algorithms to quantitatively simulate, optimize, and experimentally verify which method or combination is most effective at improving tokamak efficiency. This mathematical and computational framework enables rigorous testing before costly hardware implementation.

[1](https://arxiv.org/pdf/2306.00415.pdf)
[2](https://www.osti.gov/servlets/purl/1430529)
[3](https://www.nature.com/articles/s41586-021-04301-9)
[4](https://www.sciencedirect.com/science/article/pii/S0920379617309031)
[5](https://www.imsi.institute/activities/computational-challenges-and-optimization-in-kinetic-plasma-physics/)
[6](https://cpb.iphy.ac.cn/article/2019/1969/cpb_28_1_015201.html)
[7](https://www.sciencedirect.com/science/article/pii/S0920379623001990)
[8](https://pubs.aip.org/aip/pop/article/30/9/092510/2911814/Flexible-integrated-modeling-of-tokamak-stability)
```

## Context
- Codebase: /home/graham/workspace/experiments/extractor
- Variant: raise-the-plasma-core-density-while-maintaining-confinement-quality-by-injecting-fuel-pellets-or-modulating-fueling-rates-at-the-plasma-edge-without-triggering-disruptions
- Output Dir: /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-183850/instances/codex_01_raise-the-plasma-core-density-while-maintaining-confinement-quality-by-injecting-fuel-pellets-or-modulating-fueling-rates-at-the-plasma-edge-without-triggering-disruptions
## Gamified Rules (Summary)
- Plateau: epsilon=0.15, window=5
- Max iters: 8
- Scoring (internal per-iteration): correctness/speed/robustness/brevity -> 100 total

## Stop Condition
- Do not stop until plateau (per epsilon/window) or max iterations reached.

## Iteration Contract
- If the function for this approach is missing, implement it.
- Run the benchmark; capture stdout/stderr; compute metrics.
- Write a well-formatted JSON summary per iteration in the output dir: iter_XX_summary.json with score, metrics, stderr/stdout digests, and mutation info.
- Propose and apply a code change based on metrics; repeat until stop condition.

## Research MCPs (When Blocked)
- If blocked or an API/library detail is unknown, use research MCPs:
  - Perplexity Ask: craft a precise query; return concise, citation-backed notes.
  - Context7 Docs: fetch official docs for the relevant library/API and summarize key constraints.
- Keep research minimal and targeted to unblock; cite sources when applicable in logs.
- Do not stall the iteration loop waiting for exhaustive research; prefer incremental, testable changes.

## Benchmark Parameters
- Scales/trials: S=6x5, M=200x5, L=2000x5; L timeout=2000ms

## Execute Exactly (non-interactive)
Run this command now. When it exits, you are done:
```
python scripts/variant_agent.py --approach raise-the-plasma-core-density-while-maintaining-confinement-quality-by-injecting-fuel-pellets-or-modulating-fueling-rates-at-the-plasma-edge-without-triggering-disruptions --bench bench/multiply_benchmark.py --baseline src/core/multiply.py --variants /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-183850/instances/codex_01_raise-the-plasma-core-density-while-maintaining-confinement-quality-by-injecting-fuel-pellets-or-modulating-fueling-rates-at-the-plasma-edge-without-triggering-disruptions/variants.py --out-dir /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-183850/instances/codex_01_raise-the-plasma-core-density-while-maintaining-confinement-quality-by-injecting-fuel-pellets-or-modulating-fueling-rates-at-the-plasma-edge-without-triggering-disruptions --epsilon 0.15 --window 5 --max-iters 8 --run-id show-20250915-183850 --prompt-file /home/graham/workspace/experiments/extractor/workspace/runs/show-20250915-183850/instances/codex_01_raise-the-plasma-core-density-while-maintaining-confinement-quality-by-injecting-fuel-pellets-or-modulating-fueling-rates-at-the-plasma-edge-without-triggering-disruptions/prompt.md --api-base http://127.0.0.1:54143
```

## Monitoring
- Web logs: http://localhost:5199
- API scoreboard: http://127.0.0.1:54143/scoreboard?run_id=show-20250915-183850
- API episodes (latest): http://127.0.0.1:54143/episodes?run_id=show-20250915-183850&variant=raise-the-plasma-core-density-while-maintaining-confinement-quality-by-injecting-fuel-pellets-or-modulating-fueling-rates-at-the-plasma-edge-without-triggering-disruptions&limit=1
- API logs (tail): http://127.0.0.1:54143/logs?run_id=show-20250915-183850&variant=raise-the-plasma-core-density-while-maintaining-confinement-quality-by-injecting-fuel-pellets-or-modulating-fueling-rates-at-the-plasma-edge-without-triggering-disruptions&limit=50
- Note: Codex harness may terminate long-lived parents; rely on web logs for progress.