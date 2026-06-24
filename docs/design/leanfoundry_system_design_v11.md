# LeanFoundry
## Full System Design — v11

> **v11.12 (2026-06-24):** Path-A core is now implemented end to end: schema,
> sorry/admit rejection, render-free runtime extraction, SQLite replay store,
> and driver wire-up. The top-level search result contract remains strict:
> `SearchStatus.PROVED` means the optional rendered whole-proof artifact passed
> final `/exec/verify`; per-node policy/value artifacts may still be emitted
> from structurally solved runtime trees when rendering or verification fails.
> The v0 tree selector is the implemented local root-to-leaf PUCT/hardest-child
> descent; the global highest-UCB/LCB formulation remains reference material,
> not the current contract.

> **v11.11 (2026-06-24):** Contract 7 is updated for the Path-A training data
> baseline. Per-node policy/value data is grounded by accepted `/exec` step
> transitions and a sorry/admit rejection guard, not by whole-proof
> `rendered_lean` verification. Final `/exec/verify` remains required for
> optional whole-proof artifacts and sampled soundness audits. `PolicyExample`
> carries both the Markovian `state` and a prompt-ready `proof_prefix` string;
> whole-tree-to-surface rendering is not a training-data gate. The durable proof
> verification flag is backend-neutral (`verified_by_backend`), not
> kimina-named.

> **v11.10 (2026-06-23):** The `lean-client` lock was refreshed to kimina
> commit `310e6c13`. Kimina's dev server launch defaults now size worker count
> from CPU and available memory, then derive in-flight and queued request caps
> from that worker count. LeanFoundry must still treat `/exec/limits` as the
> runtime truth and avoid duplicating launch-default arithmetic inside search.

> **v11.9 (2026-06-21):** The first operational/extraction/lifecycle slice
> landed. `EnvBackendConfig` forwards lean-client's existing
> `max_overloaded_retries` and `overload_backoff_seconds` knobs; LeanFoundry
> still has no search-loop overload retry. Training extraction now returns an
> explicit `TrainingArtifacts` envelope with proof candidates, policy examples,
> value labels, failures, and diagnostics. That slice initially gated
> proof/policy/proved-value artifacts on final `/exec/verify`; v11.11 supersedes
> the policy/value part with the Path-A per-step data gate. Root-runtime-`OPEN`
> attempts become top-level `EXHAUSTED` and may emit only effort-gated censored
> value labels.
> `SearchAttemptContext` is runner-owned and carries separate
> `search_item_id`/`verify_item_id`; tree search cleans checked search state
> after verification, while cancelled runner tasks cancel and retry cleanup for
> the search item. The proof renderer remains canonical and narrow; richer
> identity-based focusing is still future work.

> **v11.8 (2026-06-21):** The next lifecycle and extraction slices need explicit
> contracts before code changes. Overload retry should be a backend/client config
> pass-through (`max_overloaded_retries`, `overload_backoff_seconds`), not a
> second search-loop retry. Checked cleanup requires `EnvBackend.cleanup(...)`
> and `cancel(...)` to return the concrete lean-client wire models so the runner
> can see `deleted`/`deferred` and cancel statuses. Training extraction should
> return an explicit artifact envelope carrying proof candidates, policy
> examples, value labels, rendering failures, and diagnostics, with theorem,
> attempt, verification, model-version, and effort context. Do not hide those
> artifacts in `ProofTree` or scalar `SearchResult.diagnostics`.

> **v11.7 (2026-06-21):** v0 does not distinguish runtime `OPEN` from runtime
> `EXHAUSTED`, because LeanFoundry has no durable resume path and no deliberately
> finite per-state LM action source. Runtime OR-state statuses remain
> `OPEN | PROVED | DISPROVED`. A root that is still `OPEN` when the configured
> attempt budget stops becomes the top-level `EXHAUSTED`/unproved attempt
> outcome. That outcome may produce effort-gated censored value negatives, but no
> policy positives and no mathematical falsity claim. `DISPROVED` is reserved for
> synthetic negation/inversion or another future semantic falsity certificate.

> **v11.6 (2026-06-21):** The next extraction slice must be training-artifact
> extraction, not merely solved-proof projection. The current
> `extract_proof_tree(...)` is a narrow helper for one proved proof candidate
> before final verification: it does not emit `DISPROVED` labels,
> root-unproved censored negatives, or alternative proved actions. Multiple
> proved actions can exist at one OR state because one expansion sends a tactic
> batch and attaches every executed result before the outer loop can stop on
> `PROVED`. The training extractor must therefore make the policy/value contract
> explicit: verified proved paths produce proof/policy data and value label 1;
> disproved states produce full-weight value label 0 with `disproved=true`;
> root-open-at-stop unproved attempts may produce effort-gated censored value
> label 0. Rendering remains a separate unresolved compiler problem from proof
> tree to Lean text.

> **v11.5 (2026-06-21):** Operational and terminal-state semantics are now fixed
> for the next implementation slice. Mixed `overloaded` plus executed tactic
> statuses for one step item is a backend protocol failure: charge the tactics
> that actually ran, discard partial attachments, and fail the theorem attempt.
> All-overloaded is backpressure, not search evidence. LeanFoundry should wire
> the existing lean-client retry/backoff knobs (`max_overloaded_retries`,
> `overload_backoff_seconds`) through backend config instead of adding a second
> search-loop retry layer. Those retries are outside `max_tactic_calls` and
> outside value-label effort accounting. If all-overloaded is still returned
> after that retry layer is exhausted, the result is an operational error, not
> `EXHAUSTED`. `invalid_state_token` fails immediately in v0; token
> re-derivation/restart waits for durable replay/resume. Runtime OR-states should
> distinguish only structural `OPEN`/`PROVED` from semantic `DISPROVED`; the
> top-level `EXHAUSTED`/unproved outcome is just root `OPEN` at attempt stop.
> Proved states train policy/value only after final verification, disproved
> states are full-weight value negatives, and unproved attempt outcomes are
> effort-gated censored value negatives.

> **v11.4 (2026-06-21):** Runtime tree initialization uses one synthetic root
> OR-state and one synthetic initialization AND-action above the real
> backend-created initial proof states. This is only a tree-shape device so the
> same AND/OR status rule handles one or many initial holes. `ProofTree`
> extraction skips the synthetic layer: each `ProofTree.roots` entry is built
> from a real initial backend state, paired with the proved tactic selected at
> that state.

> **v11.3 (2026-06-21):** The first concrete search-engine loop slice landed:
> direct whole-proof search and AND/OR tree search now sit behind a
> `build_engine(config)` factory. The tree wedge takes a pluggable selection
> strategy and uses product backup for AND-action child values plus max backup
> for OR-state action values; terminal status still comes from the structural
> tree, and final `/exec/verify` remains the acceptance gate. Graph/MCGS,
> negation pruning, HER, real model adapters, and bonded value-label emission
> remain deferred. The first extractor intentionally rejects split actions with
> a multi-goal focused child, rather than emitting a misleading one-bullet Lean
> script; richer group-focus rendering is deferred. Direct whole-proof search
> uses its own `max_direct_candidates` / `direct_candidates_per_round` budget
> fields, separate from tree-search `max_tactic_calls`. Tree-selection
> hyperparameters are explicit config fields: `puct_exploration_weight` and
> `best_first_missing_value_score`.

> **v11.2 (2026-06-19):** v0 search is AND/OR **tree** search, not graph search.
> States reached by different paths are **not merged**, because sound merging
> needs a state-identity fingerprint that captures Lean state the pretty-print
> omits — a hard, unsolved problem — and merging is only an optimization, not a
> correctness requirement. Consequence: `FactorizedProofState` is reduced to the
> minimal tree-search node (open goals + resume token). The merge-identity
> fields (`theorem_header_options_hash`, `tactic_history_hash`,
> `metavariable_coupling_groups`, `local_context_by_component`) are removed, and
> goals are referenced by position rather than a string id. Metavariable
> coupling is read from the backend response at expansion time to decide goal
> bundling, then discarded — not stored. The v0.3 graph-merging canonicalization
> in §3.1 is not pursued unless a validated fingerprint is built. See §3.1.

> **v11.1 (2026-06-17):** Clarifications from an interface walkthrough, folded
> into the gaps and deployment sections (no architectural change):
> - **G2** is a *label-representation* gap (the durable schema cannot encode
>   disproved-vs-censored, so the bit is lost at write time), distinct from the
>   *weight* of a censored negative, which is the tunable in R3.
> - **G3**'s `TacticNode` tree is **not** a second live structure. It is a
>   projection *extracted* from the live AND/OR search graph for one solved
>   slice at data-emission time. Two custom classes are required: the AND/OR
>   search graph (the live engine) and the small `TacticNode` tree (the
>   serialized/rendered proof). See §3.1 and A.5.
> - **G4** only bites the flywheel path: cold-start extracted data (LeanDojo/
>   LeanTree) carries no model-authored inline comments; comments are produced
>   by the policy *during search*, and the gap is "do not strip them at record
>   time." Honoring it now is free.
> - **G5** is gated **per-theorem on provenance** (`TheoremSpec.source`, already
>   present as `theorems.source`): default **off** for known-true targets
>   (leandojo/mathlib/minif2f), turned **on** for autoformalized and speculative-
>   decomposition statements where falseness is plausible. A Lean proof *state*
>   holds a *list* of goals; OR is over candidate actions, AND is over the
>   subgoals one action produces — the single-goal restriction exists because
>   `¬P` is only a clean action when there is one goal. See §3.5.1.
> - **Deployment**: the **Docker image is the prioritized path** (it seals the
>   Lean toolchain + Mathlib build, the real cost). `lean_client.launch_server`
>   only works inside this monorepo and is dev-only; downstream LeanFoundry runs
>   the server out-of-band and connects over HTTP. `connect()` round-trips
>   `GET /exec/limits` (and rejects unbounded caps), which doubles as the
>   connectivity check before any work. See Development Workflow.

> **v11 (2026-06-17):** Adds Part V / Extension D — a controlled algorithm
> ablation study (whole-proof outcome-only training vs. search-as-discovery
> vs. search-with-shaped-credit, MCGS+HER+value) run under a frozen
> theorem-to-round curriculum and a compute-matched evaluation design. This
> is additive and decoupled: Stages 2-4 of the core training pipeline keep
> their existing dynamic frontier filtering and adaptive exit criteria
> unchanged, as the production "how far can we go" recipe. Extension D is a
> separate, smaller-scale study that answers a different question — which
> algorithm produces a better prover at matched compute, and why — using its
> own frozen buckets and its own arms. See §25-32.

> **v10 (2026-06-09):** §2 reconciled with the shipped `/exec` backend —
> structured `goals` (`GoalInfo`) and `messages` (`ExecMessage`), per-result
> `diagnostics`, the new `/exec/verify` warm-pool certification endpoint
> ("path C"), and the `LEAN_SERVER_MODE=verify|exec` mode split. Throughout
> this document, references to "strict `/verify`" / "Kimina re-verification"
> for *proof* acceptance now mean `/exec/verify` in exec mode; the REPL
> `/verify` is verify-mode-only and used for autoformalized *statement*
> checks (Extension B). The client surface is now the single
> `AsyncLeanExecBackend` façade, and the server always runs as a **separate
> process** (Docker image or `python -m server`) reached over HTTP — never
> launched in-process by the client. Training, search, and roadmap design are
> unchanged from v8/v9.

---

## Project Branding

This project is called **LeanFoundry**.

LeanFoundry is a distributed high-performance Lean proof-search runtime
for search-based theorem-proving agents. It is not a single model,
dataset, or training recipe. Its purpose is to turn Lean into a scalable
execution substrate for training-time search, Expert Iteration, verifier-
guided data generation, and evaluation.

The infrastructure repo is model-agnostic and training-agnostic. Any
policy model, value model, search algorithm, or RL/SFT pipeline should
be able to plug into it through stable interfaces.

> **LeanFoundry is a distributed Lean proof-search runtime: stateless
> tactic execution, high-throughput verification, search orchestration,
> trajectory capture, and evaluation for training theorem-proving agents.**

The training repo is a separate demonstration built on LeanFoundry. It
uses one concrete recipe — currently Qwen3.6-27B + Slime + SGLang +
SFT/Expert Iteration/GRPO — to prove that the infrastructure works.
LeanFoundry should not be tethered to this recipe. The infra repo owns
execution, search, replay, and evaluation. The training repo owns model
choice, optimizer, curriculum, and experiment configuration.

---

## Open Questions and Concerns

This section is the live record of unresolved design decisions, empirical unknowns, and confirmed gaps. Anything here must be resolved or explicitly deferred before the relevant component is considered production-ready.

---

### Resolved Baseline Gaps and Remaining Design Gaps

**G1 — TheoremSpec.initial_lean_block exists (resolved baseline).**
`TheoremSpec.initial_lean_block: str | None` is now part of the in-memory
theorem request and theorem table. When set, tree search initializes from that
Lean block through `/exec/create_states`; when absent, it initializes from the
single theorem statement as before. MCGS graph semantics remain deferred, but
the sorry-initialized input surface is no longer missing.

**G2 — state_value_labels distinguishes disproved from censored negative (resolved baseline).**
`ValueLabel` and `state_value_labels` now carry both `weight` and `disproved`.
A state marked DISPROVED via future negation pruning is definitively
mathematically false — label=0 at full weight. A state searched but not proved
is a censored negative — reduced weight because "not found by this policy" is
not the same as false.

The remaining open question is not representation; it is the downstream
reward-shaping knob for censored negatives (R3).

**G3 — trajectory tactic_sequence stores the solved tree projection (resolved baseline).**
After a `cases` or `constructor` tactic producing multiple subgoals, the proof
is a branching tree. A flat list of `(state, tactic)` pairs cannot represent
this structure and cannot reconstruct Lean's branching syntax. LeanFoundry now
uses a `TacticNode` tree projection for solved proof slices:
```python
@dataclass
class TacticNode:
    state: FactorizedProofState
    tactic: str
    children: list["TacticNode"]  # AND-children after split; single child for linear step
```
Depth-first traversal yields flat `(state, tactic)` pairs for policy SFT. Any
proved subtree is a future HER candidate. `rendered_lean` is optional Path-B
artifact text for final verification, not a Path-A data gate.

This does **not** mean maintaining a second live structure in parallel with the search graph. There are two distinct structures with two distinct lifetimes, and both are custom (no off-the-shelf library provides them):

1. **The live AND/OR search graph** — the engine's working structure (OR over a state's candidate actions, AND over the subgoals one action produces; a DAG once MCGS merging is on). It holds *everything*: dead branches, failed tactics, censored states, visit counts, value estimates. It is checkpointed to disk only for operational resume (P10); it is not training data. This is a substantial custom class — the heart of the Search Engine.

2. **The serialized `TacticNode` tree** — a *projection* extracted from the solved slice of the search graph at data-emission time, then written to `trajectories.tactic_sequence`. It is trivially custom (the 3-field dataclass above). A tree, not the graph, because (a) rendering to Lean text is inherently tree-shaped (`case inl => … case inr => …`), and (b) HER's "every proved *subtree* is a candidate" is only well-defined on a tree — a merged DAG node has several parents and no unambiguous subtree.

The remaining extraction work is node-general HER and richer Path-B rendering;
the baseline durable representation is no longer a flat list.

**G4 — Inline comments must be preserved in tactic SFT data.**
Aristotle's policy generates (hidden CoT) + (inline comment) + (tactic). Inline comments persist in the action history and serve as external persistent memory — future calls to the policy see the earlier reasoning context embedded in the proof. If SFT data strips comments from action strings, the model never learns to produce them and loses this mechanism. Fix: ensure the action string recorded in trajectories includes the full text the model generated, comments included. The prompt builder in the training repo must reconstruct the full prefix including comments for policy training.

Scope note: comments do not exist in cold-start extracted data (LeanDojo/LeanTree proofs are human/extracted and carry no model-authored CoT comments), so G4 has no effect on Stage 1 SFT from those sources. Comments are produced by *our own policy* during search, only once it is prompted Aristotle-style to emit them; G4 is therefore a constraint on the *trajectory-recording* path of the flywheel (Stages 2+): record the model's full output verbatim so comments survive into the next round's SFT. Honoring it costs nothing now and is inert until commented generation is enabled (whether the base model emits useful comments at cold-start is a separate recipe question, adjacent to R5).

**G5 — Negation pruning is not in the current search plan.**
For each single-goal state `⊢ P`, a synthetic action should be added to the pool: prove `¬P` in the same local context. This action competes under normal UCB selection and receives a full sub-search — not a one-step check. If it succeeds, the state is marked DISPROVED and "dead" propagates upward through all parent AND-nodes, immediately eliminating them. This is Aristotle's hard-termination mechanism. Without it, provably-false subgoals are only abandoned via budget exhaustion. Fix: add negation augmentation as an optional flag in SearchEngine expansion (`try_negation: bool`, default False). Enable per-theorem by provenance (below); evaluate cost/benefit on traces before changing any default.

Semantics, to avoid two common confusions:
- A Lean proof *state* holds a **list** of goals, not one (wire type `goals: list[GoalInfo]`). After `constructor` on `A ∧ B`, one state carries `⊢ A` and `⊢ B`. Whether to split a multi-goal state into separate nodes is a *search-engine* decision (the AND-split), and per the LeanTree lesson (§3.1) metavariable-coupled goals are **not** split — so multi-goal nodes do occur. The synthetic action is restricted to single-goal states because `¬P` is only a clean single action when there is exactly one goal `P`.
- The negation is an extra entry in the state's **OR** action pool (a state is proved if *any* action proves it). A tactic never produces "OR goals": the subgoals one tactic produces are conjunctive (**AND** — all must close). OR is over *which action you choose*; AND is over *the subgoals an action spawns*.

Provenance gating (per-theorem, not global): `try_negation` defaults **False** and is set by the SearchEngine from `TheoremSpec.source` (carried from the existing `theorems.source` column — see §4.2):
- **Off** for known-true targets (`leandojo`, `mathlib`, `minif2f`): every subgoal of a true theorem is itself true, so trying to disprove subgoals mostly wastes budget (and `¬P` is a *full sub-search*, retried under UCB, not one cheap step).
- **On** for `autoformalized` statements and speculative subgoal-decomposition lemmas: these can be genuinely false, and negation is how search auto-rejects wrong statements / bad decompositions. This is central to the Extension B autoformalization flywheel — but it is a *pruning* accelerator; the flywheel's engine remains HER + pass-rate bucketing.

So `TheoremSpec` must carry `source` (propagated from `theorems.source`); the engine maps source → `try_negation`. No new persisted column is required — the provenance label already exists in the data spine; it just needs to reach the in-memory spec. See R4 for the cost/benefit unknown that keeps this off by default for the LeanDojo core, and §3.5.1 for the mechanism.

---

### Needs Research (Empirical Unknowns)

**R1 — Request-level dispatcher / two-level batching design.**
Two parallelism levels exist: proof-search level (many theorem/proof-graph searches running simultaneously) and tactic-candidate level (N tactics sampled for one selected proof state). The current backend decision is that the **scheduler unit is the proof-state expansion request**, not an individual tactic. One expansion request contains `state_token + tactics[]` and leases exactly one Lean worker; that worker loads the state once and applies the tactic candidates internally. Many expansion requests from many proof graphs are then batched into one Env Backend `/exec/step_batch` request, matching Kimina's existing "one HTTP request contains many independent items" design. This avoids the bad behavior where 16 tactic candidates from one state become 16 manager jobs and cause the Kimina pool to cold-start 16 identical compatible workers.

Within one theorem, tree-search iterations remain strictly sequential —
iteration N's selection depends on backpropagation from iteration N-1. Across
theorem/proof-graph searches, expansion requests are independent and can be
batched. The concrete v0 client boundary is the `lean-client` package:
LeanFoundry's EnvBackend adapter uses the single `AsyncLeanExecBackend` façade
(which owns the HTTP client, the proof-state env, and the step batcher, sized
from `/exec/limits`), so request width and in-flight count come from the
backend's `/exec/limits` response. Remaining empirical questions are the
EnvClient microbatch window, max items per HTTP request, queue-depth
backpressure, and worker-pool sizing. These are v0 profiling parameters, not
open semantic design questions.

**R2 — HER verified multiplier vs candidate multiplier gap.**
The theoretical HER amplification (10–50× from Aristotle) assumes most proved subtrees survive standalone re-verification through Kimina. In practice, subproofs that reference outer local context will fail. The actual `her_verified_multiplier` is unknown until search-based training traces exist and node-general HER is implemented. If the gap to `her_candidate_multiplier` is large, HER's flywheel contribution is smaller than expected.

**R3 — Value function censored-negative weight.**
The current design uses weight=0.25 for censored negatives. This is a guess. If too high, the value function becomes overly pessimistic and the policy stops exploring hard states. If too low, value is uncalibrated for failing states. Requires ablation once Stage 3 search-based EI is running.

**R4 — Whether negation pruning is worth implementation cost at LeanDojo scale.**
Negation pruning pays off when a significant fraction of budget is wasted on provably-false subgoals. At LeanDojo difficulty this fraction is unknown. Recommend deferring until Stage 3 search traces can be analyzed for how often goals are unprovable.

**R5 — Dynamic CoT budget training with Qwen3.6's thinking mode.**
Aristotle trains CoT budget implicitly by only training on thinking traces that preceded successful actions. Qwen3.6-27B has native `<think>...</think>` tokens. Whether to enable thinking for tactic prediction (currently disabled by default), and how to train dynamic budget without dedicated trace infrastructure, is unresolved. Empirical ablation recommended: SFT with thinking enabled vs disabled for Format 2; measure tactic accuracy and proof discovery rate.

---

### Open Algorithmic Questions

**A1 — State canonicalization for MCGS graph merging (v0.3 gate).**
Graph merging requires a canonical identity for proof states that correctly handles metavariable coupling and global-state tactics like `aesop` and `simp_all`, which cannot be safely deduplicated. The exact canonicalization is unsolved. The gate — merging disabled until a correctness acceptance test passes — is the right response. Whether the gate can realistically be passed without excluding common Mathlib tactics is unknown.

**A2 — LeanTree version compatibility with our env_profile.**
LeanTree is built on Lean 4.19.0. Our current backend prototype pins to Lean 4.29.1 to match Pantograph. Whether LeanTree traces replay correctly under our env_profile is unknown and must be verified empirically before any LeanTree data enters training. Track A integration (dataset warm-start) in the training repo is blocked on this check.

---

### Semantic Faithfulness (Extension B Specific)

**S1 — REPL /verify is a syntactic check only.**
Autoformalized statements that pass Kimina `/verify` (with `:= by sorry`) are confirmed to typecheck — not to mean the same thing as the NL source. Known failure modes: vacuous hypothesis addition, quantifier inversion (∃∀ vs ∀∃), convention inversion, missing conjuncts, definitional mismatch. The semantic judge LLM provides a probabilistic filter but not a guarantee. Semantic faithfulness is undecidable in general. Extension B output requires human spot-checking before entering held-out eval sets.

**S2 — Formalizer + checker co-training convergence is unproven.**
The mid-term Extension B design proposes training formalizer and faithfulness checker together. Whether this loop converges is unknown. Do not invest engineering effort in it until the baseline pipeline (LLM draft → /verify → judge → staging) is producing reliable output.

---

## System Landscape

LeanFoundry's position relative to existing systems:

| System | What it is | Open? | Relation to LeanFoundry |
|---|---|---|---|
| AlphaProof (DeepMind) | Closed AlphaZero-style RL prover interacting with Lean; Nature paper reports 2024 IMO silver-medal-level performance. | no | Strong closed precedent for verifier-grounded RL; not reusable infra. |
| Aristotle (Harmonic) | Closed IMO-gold-level system with Lean proof search, informal lemma generation/formalization, geometry solver, MCGS, EI, HER, value labels, TTT, and large-scale stateless REPL infrastructure. | no | Closest north star. LeanFoundry is the open infrastructure analogue at smaller scale. |
| BFS-Prover-V2 (ByteDance Seed) | Open step-level Lean 4 prover system with multi-stage Expert Iteration, adaptive tactic filtering, periodic retraining, and planner-enhanced multi-agent tree search at inference. | model/code | Important open prover/search baseline; not a reusable Kimina/Harmonic-style stateless execution/search/replay/eval framework. |
| BFS-Prover V1 | Best-first tree-search prover with self-filtering EI and DPO from compiler feedback. | model/code | Strong algorithmic baseline for best-first search; not infrastructure-first. |
| DeepSeek-Prover-V1.5 | Lean-feedback RL plus RMaxTS-style search. | partial | Search/RL prior; not reusable execution runtime. |
| DeepSeek-Prover-V2 | Recursive subgoal decomposition and proof synthesis; open models/data. | model/data | Strong teacher/baseline; not tactic-level stateless training runtime. |
| Goedel-Prover-V2 | Whole-proof/self-correction/scaffolded data synthesis with EI/RL-style recipes and released models/code/data. | model/code/data | Strong teacher/baseline; not MCGS/stateless tactic runtime infra. |
| Kimina Lean Server | High-performance Lean verifier/server with REPL worker pool, header/body split, LRU header reuse, batch verification, and feedback extraction. | yes | Best execution substrate to fork; LeanFoundry adds tactic stepping, search, replay, EI, and eval. |
| Kimina-Prover / Kimina-Prover-RL | Whole-proof RL/formal reasoning recipe using Kimina Lean Server; public materials explicitly emphasize strong results without MCTS/value/process rewards. | model/recipe | Useful baseline and infra dependency; not training-time MCGS runtime. |
| LeanDojo / LeanDojo-v2 | Data extraction, theorem/proof-state tracing, gym/tooling, training/eval/deployment framework for Lean provers. | yes | Upstream data/tooling foundation; LeanFoundry is the high-throughput search execution and replay layer. |
| LeanTree | White-box Lean 4 proof-state factorization and dataset for intermediate states. | yes | Relevant state representation prior; not full search-training runtime. |
| nanoproof | Minimal open AlphaProof/HyperTree Proof Search-style implementation using LeanTree server, MCTS prover, and distributed RL loop. | yes | Closest open experimental prior; still not a production-grade stateless Kimina/Harmonic-style infra framework. |
| InternLM-StepProver / MPS-Prover / StepFun-Prover / Leanabell | Stepwise/tool-integrated prover systems using critics, search, verifier feedback, or RL. | mixed | Important baselines; generally model/prover pipelines rather than model-agnostic runtime infrastructure. |
| Seed-Prover 1.5 / Delta-Prover | High-performing ByteDance formal proving systems with large-scale agentic RL and test-time scaling. | proofs/project | Latest competitive reference; not open reusable infra. |
| Lean Copilot / Prover-Agent / Ax-Prover | Lean-native or agentic proof-assistant workflows using LLMs, Lean feedback, or auxiliary lemmas. | mixed | Adjacent human/agent tooling; not LeanFoundry-equivalent training-time search infrastructure. |
| **LeanFoundry** | Open distributed Lean proof-search runtime: stateless tactic execution, batch verification, search orchestration, trajectory capture, HER/value labels, replay storage, and solved@budget evals. | **yes** | Infrastructure layer, not a single prover checkpoint or one-off training recipe. |

The key gap is not "open Lean provers." Many open Lean provers now exist.
The key gap is **open, reusable infrastructure for training-time search**:
a model-agnostic runtime that exposes stateless Lean tactic execution,
high-throughput verification, MCGS/AND-OR search orchestration, trajectory
capture, HER extraction, value labels, replay storage, and reproducible
solved@budget evaluation.

Existing open systems cover important pieces of this stack, but sit at different
layers. LeanDojo is data + gym; Kimina is verifier/server infrastructure;
BFS-Prover-V2, Goedel-Prover-V2, DeepSeek-Prover-V2, Kimina-Prover,
StepFun-Prover, Leanabell, InternLM-StepProver, MPS-Prover, Seed-Prover,
DAP-style agents, Prover-Agent, and Ax-Prover are prover systems, models,
or training recipes. Harmonic's Aristotle appears closest architecturally,
but the high-performance search/runtime infrastructure is closed. LeanFoundry's
contribution is the open infrastructure layer that lets different policies,
value models, search algorithms, and training recipes plug into a common Lean
proof-search substrate.

LeanDojo remains an upstream data/tooling dependency. LeanFoundry uses
LeanDojo data and forks Kimina as the execution backend; the search engine,
trajectory capture, replay store, training-time EI integration, and solved@budget
eval framework are the net-new open infrastructure.

---

## Extensions and Roadmap

This document describes one fully designed core system and four explicitly
scoped extensions. Understanding the boundaries between them is important
for planning implementation work.

### Core System (Part I + Part II)

Single-machine infrastructure and training pipeline using LeanDojo data.
Build and validate this end-to-end before activating any extension.
All components are specified to implementation level.

### Extension A: Multi-Machine Scale-Out (Part III)
> **Status: Designed, implementation deferred until single-machine system
> is stable and producing results on LeanDojo novel_premises split.**

Reproduces Harmonic's distributed REPL infrastructure ("Running Lean at
Scale", Sep 2025). Key new component: a custom C++ REPL router providing
per-message routing, global request queueing, and autoscaling. No
algorithmic changes required — only infrastructure configuration changes.

Trigger: single-machine throughput (proof attempts per hour) is the
bottleneck, not model capability.

### Extension B: Autoformalization Data Pipeline (Part IV)
> **Status: Architecture outlined, implementation PENDING RESEARCH.
> Do not build until the core system has been trained to satisfactory
> performance on the full LeanDojo dataset.**

Converts informal mathematical statements into verified Lean 4 statements,
expanding the theorem pool beyond LeanDojo's fixed 98k theorems. Key
design decisions depend on empirical results from training runs.

Trigger: model has plateaued on LeanDojo novel_premises split, and data
diversity (not compute) is the limiting factor.

### Extension C: Test-Time Training Module (Part V, §21-24)
> **Status: Design sketch. Implement after core system is stable.**

Per-problem LoRA fine-tuning on search traces found during inference,
for olympiad-level targets with no other training signal. Evaluation-time
only; does not replace or modify Stages 1-4.

### Extension D: Controlled Algorithm Ablation Study (Part V, §25-32)
> **Status: Design sketch. Run after Stage 1 checkpoint and a hygiene-
> passed curated pool exist. Does not modify Stages 2-4.**

Holds base checkpoint, theorem-to-round curriculum, and total compute
fixed, and varies only the training algorithm (outcome-only whole-proof
EI, search-as-discovery-only, search-with-shaped-credit/MCGS+HER+value),
to answer which algorithm produces a better prover and why — a question
the production pipeline's adaptive, dynamically-filtered recipe (Stages
2-4) is not designed to answer, since its frontier and exit criteria
move with the live policy rather than staying fixed across arms.

Trigger: Stage 1 cold-start checkpoint exists and is stable; runs
alongside, not instead of, the core pipeline's own Stage 2-4 progression.

---

## System Architecture

LeanFoundry decomposes into five modules. The network topology between them
is a first-class design concern because proof search is throughput-bound:
latency on any link between Search Engine and Env Backend directly limits
proofs-per-hour.

### Single machine

```
┌────────────────────────────────────────────────────────────────────┐
│                    Single Machine  (8 × H100)                      │
│                                                                    │
│  ┌─────────────────────┐   weight sync    ┌───────────────────┐   │
│  │      Trainer        │◄────────────────►│ Inference Engine  │   │
│  │     (Megatron)      │   NVLink / NCCL  │    (SGLang)       │   │
│  │ profiled update GPUs │                  │ profiled rollout  │   │
│  └──────────┬──────────┘                  └────────┬──────────┘   │
│             │ read samples                          │              │
│             │ (local socket)                        │ HTTP         │
│             ▼                                       │ sample_tactics()
│  ┌─────────────────────┐   write A-type  ┌──────────▼──────────┐  │
│  │    Data Buffer      │◄────────────────│   Search Engine     │  │
│  │     (SQLite)        │   read B-type   │  direct / tree /    │  │
│  │                     │────────────────►│  self-correct       │  │
│  └─────────────────────┘                 └──────────┬──────────┘  │
│                                                      │             │
│  ┌─────────────────────┐          HTTP  /exec/step_batch          │
│  │     Evaluation      │◄─────────────────────────── │            │
│  │  solved@budget      │                              ▼            │
│  │  pass@k / curves    │                  ┌───────────────────┐   │
│  └─────────────────────┘                  │   Env Backend     │   │
│                                           │ Kimina/Pantograph │   │
│                                           │ profiled workers  │   │
│                                           └───────────────────┘   │
│                                                                    │
│  * GPU and worker allocation are profiled alternatives — see Phase -1            │
└────────────────────────────────────────────────────────────────────┘
```

### Cluster (Extension A)

```
  Training Nodes                      Inference Nodes
  ┌───────────────────────┐           ┌───────────────────────┐
  │  Trainer (Megatron)   │◄─────────►│  Inference Engine     │
  │  multi-GPU, NCCL/IB   │ weight    │  SGLang cluster       │
  │                       │ sync TCP  │  Slime-managed        │
  └───────────┬───────────┘           └───────────┬───────────┘
              │ TCP                               │ HTTP
              ▼                                   │ sample_tactics()
  ┌───────────────────────┐   write   ┌───────────▼───────────┐
  │    Data Buffer        │◄──────────│   Search Engine       │
  │  PostgreSQL /         │   read    │   CPU nodes           │
  │  Redis Streams        │──────────►│   search orchestration│
  └───────────────────────┘           └───────────┬───────────┘
                                                  │ TCP
                                                  ▼
                                      ┌───────────────────────┐
                                      │   Env Backend         │
                                      │  Kimina/Pantograph    │
                                      │  + C++ REPL Router    │
                                      │  CPU-only preemptible │
                                      └───────────────────────┘

  ┌──────────────────────────────────────────────────┐
  │  Evaluation  (separate; reads from Data Buffer)  │
  └──────────────────────────────────────────────────┘
```

Network links and their throughput relevance:

```
Search Engine ↔ Env Backend      /exec/step_batch over HTTP/TCP
  Critical path. Every proof-state expansion in MCGS traverses this link.
  Latency p95 directly bounds proofs-per-hour.
  Single machine: localhost, ~0.1ms.
  Cluster: TCP to REPL router, target <5ms p95.

Search Engine ↔ Inference Engine  PolicyClient over HTTP
  Called once per MCGS node expansion (sample N tactics).
  Batching amortizes cost. Less latency-sensitive than Env Backend link.

Trainer ↔ Inference Engine        weight sync via NVLink/NCCL
  Triggered after each training update.
  Must complete before next search round starts (in concurrent mode).
  Single machine: NVLink, fast. Cluster: TCP, can be pipelined.

Search Engine ↔ Data Buffer       write A-type, read B-type
  Write path: after each proof found (low frequency).
  Read path: theorem batch fetch at round start (low frequency).
  Not on the critical latency path.
```

---

## Design Principles

From a systems RL engineering perspective, the following principles govern
every design decision in LeanFoundry. They are listed here so that future
contributors can evaluate trade-offs against a consistent set of values.

**P1 — Decouple rollout from optimization.**
Data generation (search, rollout) and gradient updates have different
resource profiles (CPU + Lean env vs GPU) and different failure modes.
Mixing them in one process means one failure drags down the other. Separate
processes allow independent scaling and independent restart.

**P2 — Stateless workers.**
Any process executing tactics, serving inference, or processing data must
carry its state in the request or in a backend-owned state token, not in the
process. In the single-node Env Backend, `state_token` resolves to a local
tmp/shared Pantograph state file; no public API exposes process-local
Pantograph `state_id`. Worker death loses no search state. This is the
prerequisite for preemptibility and horizontal scaling.

**P3 — Durable data spine.**
The Data Buffer is the single source of truth. All discovered proofs and
training samples only "exist" once durably written to it. Every other
module is reconstructible from the Data Buffer. This determines the
storage technology: WAL-mode SQLite on single machine, PostgreSQL at
cluster scale — never in-memory queues as the primary store.

**P4 — Algorithm-agnostic interfaces.**
`/exec/step_batch` does not know whether MCGS or beam search is calling
it. `PolicyClient` does not know which search algorithm is using it.
`RLEngineBase` does not know whether Slime or another framework implements
it. Each interface expresses only its minimum contract. Components can be
swapped without modifying their callers.

**P5 — Critical path latency is a first-class metric.**
The Search Engine ↔ Env Backend link is on the critical path of every
node expansion. Its p95 latency directly bounds proofs-per-hour. This is
not an afterthought — it drives protocol choice (HTTP vs gRPC vs shared
memory), worker count, and NUMA affinity configuration.

**P6 — Training stability over throughput.**
Reward hacking, distribution collapse, and data contamination are more
dangerous than slow throughput. `env_profile` enforcement, axiom
validation, and curriculum controls are non-negotiable correctness
guarantees. Specific algorithmic mechanisms (regularization terms,
constraint strengths) are determined empirically, not prescribed here.

**P7 — Profile before committing.**
Phase -1 exists because memory pressure, GPU allocation, and sequence
length interact in ways that cannot be predicted analytically. No
training begins without a completed `resource_profile_manifest.json`.
Commitments made before profiling are hypotheses, not decisions.

**P8 — The data flywheel compounds.**
Every design decision should ask: does this accelerate the flywheel or
cap it? Better model → better search prior → more proofs discovered →
better training data → better model. HER is a flywheel accelerator
(10–50× data at zero Lean cost). Pass-rate bucketing ensures each EI
round trains at the capability frontier. Autoformalization prevents the
flywheel from stalling when LeanDojo signal is exhausted.

**P9 — Explicit complexity escalation.**
Extensions A, B, C are not "future work" — they are upgrades with
explicit trigger conditions:
- Extension A (cluster scale-out): single-machine search throughput is
  the measured bottleneck
- Extension B (autoformalization scale): model plateaus on LeanDojo
  novel_premises split
- Extension C (test-time training): core pipeline is stable
Complexity before the trigger condition is premature and pollutes the
design with requirements that don't exist yet.

**P10 — Preemptibility is a correctness property, not a performance
optimization.**
Any module must be killable at any time without data loss or search
progress loss. On single machine this means: process isolation (not
threads), MCGS graph checkpointing to disk, atomic weight sync writes,
Data Buffer WAL, and PolicyClient auto-reconnect. These are designed in
from the start; retrofitting preemptibility is expensive.

---

# Part I: Reusable Infrastructure

---

## 1. Environment Profiles

Every Lean execution is tied to a specific environment profile. This is
not optional bookkeeping — mixing data across Mathlib versions silently
corrupts training data because tactics that work on one commit may fail
on another.

An environment profile is:

```python
@dataclass
class EnvProfile:
    lean_version: str          # e.g. "4.29.1"
    mathlib_commit: str        # full git SHA
    imports: list[str]         # e.g. ["Mathlib", "Aesop"]
    header: str                # full import header string
    header_hash: str           # sha256 of header (used for LRU keying)
    loogle_index_path: str     # version-pinned, built from same commit
    premise_index_path: str    # version-pinned
```

Rules:
- Every A-type training sample must have a verified env_profile field
- Env Backend scheduler uses header_hash for LRU routing
- Never mix env_profiles in a single training batch
- When consuming external data (Goedel, DeepSeek proofs), re-verify
  under our own env_profile before adding to training set

Default env_profile for the current backend prototype: Lean 4.29.1 +
Mathlib at commit `5e932f97dd25535344f80f9dd8da3aab83df0fe6`, chosen to
match the tested Pantograph version. All data generation uses one pinned
profile. Update only between major training phases.

---

## 2. Kimina `/exec` Env Backend

### 2.1 What Kimina Already Has

Kimina Lean Server (project-numina/kimina-lean-server) provides:
- A pool of pre-started REPL worker processes
- Routing of requests to idle workers
- LRU cache keyed by import header: workers pre-loaded with Mathlib
  are reused across requests with the same header, avoiding repeated
  ~60s Mathlib import overhead
- Whole-proof batch verification endpoint (/verify) — REPL/verify-mode only
- Infotree extraction (tactic state annotations) — REPL/verify-mode only

This is the infrastructure we build on. We do NOT build a separate
LeanStepServer. The Env Backend adds `/exec` proof-state stepping,
verification, cleanup, and cancellation while keeping the server-owned
scheduler/worker lifecycle.

### 2.2 Current Backend Decision: Kimina Pool + Pantograph Worker

The v0 Env Backend is a fork/adaptation of Kimina Lean Server, but the
tactic-level worker is Pantograph. Kimina contributes the service shell:
FastAPI endpoints, batch request handling, a capped free/busy worker pool,
exact-header reuse, idle LRU eviction, timeouts, diagnostics, and `/verify`.
Pantograph contributes the proof-state operations Kimina's REPL interface
does not currently expose: `goal_start`, `load_sorry`, `goal_tactic`,
`goal_save`, and `goal_load`.

The key design correction is the scheduler unit:

```text
one proof-state expansion item = one worker lease
one expansion item = state_token + tactics[]
one worker loads the state once and tries all tactics internally
```

Do **not** flatten the `tactics[]` list into manager-level jobs. Kimina's
manager only reuses free exact-header workers. If tactic candidates were
submitted independently, the first tactic would take the only compatible free
worker, and the second tactic would see no free match and cold-start another
identical compatible worker until `max_repls` is reached. That is correct for
independent `/check` code-check items, but wrong for one proof-state expansion.

The implementation boundary is intentionally narrower than the server internals:
LeanFoundry depends on the `lean-client` Python package and talks to a running
server over HTTP. It does not import `server.settings`, `server.main`,
`PantographManager`, or backend worker classes. The only place that may mention
Kimina by name inside LeanFoundry is a small EnvBackend adapter/launcher module;
the SearchEngine sees an `EnvBackend` interface, not a concrete server.

### 2.2.1 Server Mode: verify | exec

The server boots in exactly one mode, selected by `LEAN_SERVER_MODE` (default
`exec`). A search/RL deployment runs **exec mode**: it constructs only the
Pantograph worker pool + state store and mounts `/exec/*` (including
`/exec/verify`) + `/health`; the legacy REPL routes (`/api/check`, `/verify`)
are not mounted. A batch-verification deployment runs **verify mode**: the Lean
REPL pool + `/api/check` + `/verify`, with no Pantograph pool. One process never
constructs both stacks. Search-path proof acceptance therefore uses
`/exec/verify` (§2.7), not the REPL `/verify`. In all cases the server runs as a
**separate process** — its Docker image or `python -m server` from a checkout —
reached over HTTP; the client (§3) never launches it in-process.

### 2.3 State Representation: Opaque Token, Local Tmp File Backing

For the single-node system, the public protocol carries an opaque
`state_token`, not a serialized blob and not a raw filesystem path. The backend
owns a local state store:

```text
state_token -> /dev/shm/leanfoundry-state/<env>/<hash>.state
```

The backing file is Pantograph's serialized goal state, produced by
`goal_save` and restored by `goal_load`. The token metadata records:

```python
@dataclass
class StateRecord:
    token: str
    path: str
    env_profile: str
    header_hash: str
    lean_version: str
    mathlib_commit: str
    imports: list[str]
    raw_bytes: int
    created_at: float
    last_accessed_at: float
    ttl_seconds: int
```

Why token-over-blob for v0:
- Single-node workers can all read the same local file path.
- We avoid sending and writing the same state bytes repeatedly.
- The API remains portable: later multi-node mode can resolve the same token
  through a content-addressed object store or shared filesystem.

The backend may expose debug/export endpoints for blob materialization, but
normal proof search uses `state_token`.

### 2.4 Request Semantics: Batch Across States, Not Across Tactics

`/exec/step_batch` is batch-first like Kimina `/check`, but the batch item is
a proof-state expansion request rather than an independent whole-code check.

```text
HTTP request
  item 0 -> one worker -> load S0 once -> try 16 tactics -> return children
  item 1 -> one worker -> load S1 once -> try 16 tactics -> return children
  ...
```

This provides parallelism across proof graphs / selected frontier states while
keeping all tactic candidates for one state inside one worker lease.

### 2.5 Worker Procedure

For each expansion item:

```python
async def step_item(worker: PantographWorker, item: StepItem) -> StepItemResult:
    base = worker.goal_load(state_store.path(item.state_token))
    results = []
    for tactic in item.tactics:
        try:
            child = worker.goal_tactic(base, tactic)
            child_token = state_store.save(worker, child)
            results.append(StepResult(
                tactic=tactic,
                status="complete" if child.is_solved else "open",
                state_token=child_token,
                goals=child.goals,    # structured GoalInfo objects, not strings
            ))
        except TacticFailure as err:
            results.append(StepResult(tactic=tactic, status="error", messages=err.messages))
    return StepItemResult(node_id=item.node_id, results=results)
```

The worker must delete temporary in-process goal states after each item to keep
Lean memory stable. A `complete` status here means the tactic closed the goals
in the interactive session; final reward-grade acceptance still requires
`/exec/verify` (full standalone compile + `#print axioms`), which rejects
`sorry`/`sorryAx` and disallowed axioms (§2.7).

### 2.6 Scheduler Policy

The scheduler is Kimina-shaped:

```text
Priority order for worker selection:
  1. free worker with matching env_profile + header_hash
  2. if total workers < max_repls: create/prep a new worker
  3. if pool full and some worker is free: evict oldest free worker
  4. if all workers busy: wait until release or timeout
```

Rules:
- One expansion item leases one worker.
- Never split `tactics[]` into separate manager jobs.
- Never cold-start workers on the request critical path solely to fan out one
  item's tactics.
- Prewarm duplicate compatible workers only by configuration or background
  policy, not as a hidden side effect of one tactic batch.
- Worker count is memory-budgeted and empirically profiled. Kimina's dev
  launcher now uses CPU plus available-memory defaults, but production
  LeanFoundry runs should still profile and override these values explicitly
  when needed.

Kimina config knobs that become first-class training config:

```yaml
env_backend:
  # The server's own launch settings (env vars / CLI flags) used when you run
  # its Docker image or `python -m server`. The client connects over HTTP; it
  # does not launch the server in-process.
  workers: ${profiled_worker_pool_size}
  max_lean_processes_per_env_profile: ${profiled_worker_pool_size}
  recommended_items_per_step_batch: ${profiled_worker_pool_size}
  recommended_in_flight_step_batches: 8
  # May be omitted for the server default:
  # max_in_flight_exec_requests = min(workers, 8)
  # max_queued_exec_requests = min(max_in_flight_exec_requests * 4, 32)
  max_in_flight_exec_requests: ${profiled_or_server_default}
  max_queued_exec_requests: ${profiled_or_server_default}
  max_state_store_bytes: 17179869184
  state_store_dir: "/dev/shm/leanfoundry-state"
  single_process: true
  state_ttl_seconds: 3600
  pantograph_project_dir: "/workspace/mathlib4"
  pantograph_imports: ["Mathlib"]
```

The launch config is app-level configuration. Search code should discover
request-shaping values from `/exec/limits`; it should not duplicate these
defaults in the SearchEngine.

### 2.7 Batch API

All endpoints are batch-first. Single-item batches are valid.

The execution API is search-algorithm-agnostic. The search algorithm
(MCGS, beam search, direct sampling, etc.) lives entirely in the Search
Engine / rollout. Env Backend executes tactic steps and verifies proofs; it
knows nothing about search structure beyond opaque `node_id` correlation.

**GET /exec/limits**

Advertises enforced caps and client recommendations. LeanFoundry should call
this through `AsyncLeanExecBatcher.from_server_limits(env)` instead of hardcoding
request width or in-flight count. The client refuses unbounded safety caps.
Concrete values are server-returned; an 8-worker launch can look like:

```json
{
  "max_pantograph_workers": 8,
  "max_lean_processes_per_env_profile": 8,
  "max_items_per_step_batch": 1024,
  "max_tactics_per_step_item": 64,
  "max_attempts_per_step_batch": 8192,
  "max_create_items_per_request": 1024,
  "max_in_flight_exec_requests": 8,
  "max_queued_exec_requests": 32,
  "max_state_store_bytes": 17179869184,
  "max_acquire_timeout_ms": 600000,
  "max_step_timeout_ms": 600000,
  "recommended_items_per_step_batch": 8,
  "recommended_in_flight_step_batches": 8,
  "single_process": true,
  "cleanup_policy": "defer_while_in_flight"
}
```

**POST /exec/create_states**

Initializes Pantograph states from Lean code containing one or more sorry goals.

```json
{
  "env_profile": "lean4.29.1_mathlib_5e932f97",
  "items": [
    {
      "item_id": "thm_001:attempt_0",
      "code": "import Mathlib\n\ntheorem t (n : Nat) : n + 0 = n := by\n  sorry",
      "acquire_timeout_ms": 5000,
      "step_timeout_ms": 5000,
      "debug": false
    }
  ]
}
```

Response:

```json
{
  "items": [
    {
      "item_id": "thm_001:attempt_0",
      "status": "open",
      "states": [
        {
          "state_token": "st_root...",
          "goals": [
            {
              "target": "n + 0 = n",
              "pretty": "n : Nat\n⊢ n + 0 = n",
              "hypotheses": [{"type": "Nat", "name": "n", "value": null}],
              "name": null,
              "sibling_dep": []
            }
          ]
        }
      ],
      "messages": [],
      "diagnostics": {"acquire_ms": 12.0, "lean_ms": 340.0}
    }
  ]
}
```

**POST /exec/step_batch**

Request:
```json
{
  "items": [
    {
      "node_id": "graph7:n123",
      "state_token": "st_root...",
      "tactics": ["simp", "rw [Nat.add_comm]", "nlinarith"],
      "acquire_timeout_ms": 5000,
      "step_timeout_ms": 5000
    }
  ]
}
```

Response:
```json
{
  "items": [
    {
      "node_id": "graph7:n123",
      "results": [
        {
          "tactic": "simp",
          "status": "complete",
          "state_token": null,
          "goals": [],
          "messages": []
        },
        {
          "tactic": "rw [Nat.add_comm]",
          "status": "open",
          "state_token": "st_child...",
          "goals": [
            {
              "target": "0 + n = n",
              "pretty": "n : Nat\n⊢ 0 + n = n",
              "hypotheses": [{"type": "Nat", "name": "n", "value": null}],
              "name": null,
              "sibling_dep": []
            }
          ],
          "messages": []
        }
      ],
      "diagnostics": {"acquire_ms": 0.0, "lean_ms": 210.0}
    }
  ]
}
```

`messages` entries are structured `ExecMessage` objects
(`{severity, data, pos?, end_pos?}`); positions are body-relative and the
router applies the import-header line offset before returning them.

Additional operational endpoints:
- `POST /exec/cleanup` deletes all states for completed `item_id`s.
- `POST /exec/cancel` marks `item_id`s for cancellation.
- `GET /exec/stats` exposes state-store, lifecycle, limiter, and worker stats.

**POST /exec/verify** (warm-pool proof certification — "path C")

Reward-grade acceptance for an assembled proof runs on the same warm Pantograph
pool as stepping — no separate REPL service, no cold start. The worker compiles
the full proof standalone and appends `#print axioms <theorem_name>`, rejecting
Lean errors, `sorry`/`sorryAx`, and any axiom outside the item's allow-list. A
completed stepped state is not a sufficient certificate on its own — it does not
enumerate the proof term's transitive axiom dependencies.

Request:
```json
{
  "env_profile": "lean4.29.1_mathlib_5e932f97",
  "items": [
    {
      "item_id": "thm_001:final",
      "code": "import Mathlib\n\ntheorem foo (n : Nat) : n + 0 = n := by\n  rw [Nat.add_zero]",
      "theorem_name": "foo",
      "allowed_axioms": null,
      "acquire_timeout_ms": 5000,
      "step_timeout_ms": 10000,
      "debug": false
    }
  ]
}
```
`allowed_axioms: null` inherits the server default trusted set
(`propext, Classical.choice, Quot.sound`, via the `verify_allowed_axioms`
setting); `[]` demands an axiom-free proof.

Response:
```json
{
  "items": [
    {
      "item_id": "thm_001:final",
      "status": "accepted",
      "theorem_name": "foo",
      "axioms": [],
      "messages": [],
      "diagnostics": {"acquire_ms": 4.0, "lean_ms": 1200.0}
    }
  ]
}
```
`status` is `accepted | rejected | error | overloaded | cancelled`.

The legacy REPL **`POST /verify`** (Kimina's original
`{statements:[{id, header, proof}]}` whole-file check) still exists but only in
**verify mode** (see §2.2.1) — used for autoformalized *statement* checks
(Extension B), not search-path proof acceptance.

### 2.8 Validation Harness

Before trusting the Kimina `/exec` Env Backend for training, validate it reproduces known
proof trajectories with correct cache behavior.

For each known proof in LeanDojo:

```
1. Initialize root/sorry states through /exec/create_states
2. Replay each known tactic through /exec/step_batch
3. Compare resulting Pantograph goals to trace goals where trace data exists
4. Render final proof from collected tactic history
5. Verify final proof through /exec/verify
6. Measure state-token size, load/tactic/save latency, and cache efficiency
7. Stress queueing with many proof-state items per batch
```

Acceptance metrics:
```
init_success_rate               > 0.99
step_replay_success_rate        > 0.99
render_verify_success_rate      > 0.99
header_cache_hit_rate           > 0.90
worker_utilization              > 0.70
queue_wait_p95                  < 100ms
step_latency_p50                < 500ms
step_latency_p95                < 5000ms (some tactics are slow)
state_token_size_p50            < 5MB
goal_load_time_p50              < 200ms
```

If this harness is weak, search training produces garbage silently.
Validate before any training run.

---

## 3. Search Engine

The search engine is a Python process that orchestrates direct and tree search. It has no
Lean knowledge — it only knows about nodes, actions, values, and scores.
All Lean execution is delegated to an EnvBackend client. In the v0
implementation, that client is the `lean-client` `AsyncLeanExecBackend` façade
(one object owning the HTTP client, the proof-state env, and the step batcher);
the SearchEngine should not import `lean_client` directly.

### 3.1 Proof Tree Structure and State Equivalence

A proof is an AND/OR hypergraph:
- **Node (state)**: a `FactorizedProofState` = goal components, local
  context per component, and metavariable-coupling metadata
- **Hyperedge (action)**: a tactic applied to a state, producing zero
  or more new states
- A state is **proved** if ANY action proves it (OR)
- An action **succeeds** if ALL resulting states are proved (AND)

State semantics are owned by the **infrastructure repo**. Dataset selection is
owned by the **training repo**. This means LeanFoundry can adopt LeanTree-style
factorized proof-state semantics without hard-coding the LeanTree dataset as a
required training source.

State merging is a correctness-sensitive optimization, not a v0 assumption.
A naive hash of pretty-printed goals and local context is useful for diagnostics
but is not sufficient for correctness-critical graph merging.

Aristotle's report treats state equivalence more carefully: goal expressions,
local-context expressions, and local variable names must match; multi-goal
states are split only when there are no metavariables; and tactics with global
or search-internal state, such as `aesop`, complicate action/state equivalence.
LeanTree adds an important compatible lesson: split independent goals, but do
**not** split goals coupled by metavariables. LeanFoundry therefore gates graph
merging by version:

```
v0.1 / v0.2:
  - tree search only
  - exact textual proof-state matching for diagnostics and dedup only
  - no correctness-critical graph merging

v0.3:
  - Aristotle-compatible + LeanTree-inspired canonicalization research path
  - canonical identity includes:
      env_profile
      theorem/header/options/imports hash
      normalized goal-component expressions
      normalized local context expressions per component
      local variable names
      metavariable coupling groups
      metavariable assignments when exposed
      universe metadata when exposed
      tactic history hash for merge-unsafe tactics
  - split multi-goal states only when no metavariable coupling is present
  - mark tactics with global-state behavior as merge-unsafe unless validated

Acceptance gate:
  - every merged proof path renders to Lean and passes strict /verify
  - Pantograph state-token replay agrees with trace goals where trace data exists
  - no drop in render_verify_success_rate
  - solved@budget improves over graph-merge-off tree MCTS
```

Infrastructure-owned state schema (v0 tree search; see v11.2 note). A node
stores its open goals and the token to resume them — not how it was assembled.
The merge-identity fields and per-component context dict of earlier drafts are
removed; goals are referenced by position:

```python
@dataclass
class FactorizedProofState:
    env_profile: str
    goal_components: list[GoalComponent]   # open goals, in Lean's order
    pretty_state: str
    state_token: str | None = None
    serialized_lean_state: bytes | None = None
```

Diagnostic-only hash (not a merge key — see v11.2; merging is not done):

```python
def diagnostic_state_hash(state: FactorizedProofState) -> str:
    return sha256(json.dumps({
        "env_profile": state.env_profile,
        "pretty_state": state.pretty_state,
    }, sort_keys=True)).hexdigest()
```

The "Graph" in MCGS is enabled only after this gate passes. Until then,
PUCT tree MCTS and best-first search are the correctness baselines.

### 3.1.1 LeanTree Integration

LeanTree integration has two tracks with a strict repo boundary.

**Track A — optional dataset warm-start and validation traces**

Owner: **training repo**. The training repo decides whether to use the
LeanTree dataset, which version/split to ingest, and how much weight to give it
in SFT or critic warm-starting. The infra repo only provides normalized schemas,
replay validators, and EnvBackend APIs.

If selected by the training repo, LeanTree data can be used for:

```text
- Stage 1 tactic-policy SFT
  input  = factorized proof state / goal component
  target = next tactic edge

- Value/critic warm-start
  weak labels from proof_depth, proof_size, solved subtree structure

- Env Backend validation
  replay LeanTree proof-tree edges through /exec/step_batch
  compare resulting post-tactic FactorizedProofState
```

Known public dataset facts to verify at ingest time: the Hugging Face dataset
card lists LeanTree as CC-BY-4.0; describes sources from Mathlib 4.19.0 and
DeepSeek-Prover-V1; reports 74,706 factorized tactic proofs from Mathlib and
26,201 from DeepSeek-Prover-V1; and exposes node fields including
`proof_size`, `proof_depth`, tactic edges, goal types, hypotheses, imports,
open namespaces/context, and source spans.

Do **not** create a LeanTree-specific HER or curriculum stage. HER remains a
general LeanFoundry EI mechanism over whatever verified Stage 2/3 proofs are
discovered. LeanTree metadata may help audit or weight samples, but it is not a
separate HER pipeline.

**Track B — factorized state semantics for search**

Owner: **infrastructure repo**. LeanTree informs the `FactorizedProofState`
abstraction used by the search engine: goal components, local context per
component, metavariable coupling groups, tactic history hash, pretty state, and
optional serialized Lean state. This replaces the old `goals + local_context`
hash direction for MCGS state identity.

Kimina remains the online backend:

```text
LeanFoundry EnvBackend = Kimina-style high-throughput serving
                         + LeanTree-style factorized proof-state semantics
```

Kimina owns online serving, batching, header LRU, verification, worker
profiling, and `/exec/step_batch`. LeanTree contributes offline data format,
proof-tree extraction ideas, factorization semantics, and validation targets;
LeanFoundry does not run a separate LeanTree server beside Kimina in the core
system.

Pre-integration checks are split by owner:

```text
Training repo checks:
  - exact dataset version, size, source split, license, file format, fields
  - whether proof_depth/proof_size are present per node
  - raw whole-state tactic SFT vs factorized-state tactic SFT
  - prompt length reduction
  - tactic validity / next-tactic accuracy
  - value warm-start impact on tree solved@budget

Infra repo checks:
  - can LeanTree traces replay under our env_profile?
  - how many samples fail after Kimina re-verification?
  - does LeanTree require Lean 4.19 or support our Lean/Mathlib version?
  - how LeanTree detects metavariable coupling
  - whether global tactics like aesop/simp_all create unsafe splitting cases
  - whether state equivalence is strong enough for MCGS merging
```

Integration path:

```text
1. training repo ingests LeanTree dataset offline, if selected
2. infra replay validator replays traces through Env Backend
3. only after replay validation, port factorized_state into /exec/step_batch
4. only after state-equivalence validation, enable MCGS graph merging
```

### 3.2 AND/OR UCB Selection

The v0 implementation uses local root-to-leaf PUCT descent over the AND/OR tree.
At an OR state, PUCT chooses one action using prior, value, visits, and
`puct_exploration_weight`; at an AND action, search descends into the hardest
open child using the implemented structural heuristic (more open goals, fewer
visits, then stable order). The older global highest-UCB plus LCB-hardest-child
formulation is reference material, not the current contract.

```python
def select(tree: SearchGraph) -> FactorizedProofState:
    node = tree.root
    while node.is_expanded:
        action = best_puct_action(node)
        if not action.children:
            return node
        node = hardest_open_child(action)
    return node

def ucb_score(action, c_explore=1.0):
    exploit = action.value_estimate
    explore = c_explore * action.prior * (
        sqrt(action.parent.visit_count) / (1 + action.visit_count)
    )
    return exploit + explore
```

### 3.3 Tree Expansion

Tree-search iterations within a single theorem are strictly sequential: each
iteration's UCB/LCB selection depends on backpropagation from the previous
iteration. At expansion time, the policy samples N candidate tactics for the
selected proof state. These N tactics form one Env Backend expansion item:
`state_token + tactics[]`. The backend must not schedule those tactics as N
independent manager jobs; one worker loads the state once and evaluates the
candidates internally.

Parallelism comes from batching many such expansion items across concurrent
proof graphs / theorem searches. The EnvClient coalesces those items into
`/exec/step_batch` requests, and the Kimina-style backend executes items in
parallel up to the worker-pool cap.
See concern R1 for cross-theorem batching.

The policy prompt must include the full action history with inline comments
preserved — comments are persistent memory across the proof (see concern G4).

```python
async def expand(state: FactorizedProofState, model_client, env_client, n_tactics=8):
    # 1. Sample N tactics in one batched call
    #    Prompt includes full tactic history WITH inline comments (see G4)
    tactics = await model_client.sample_tactics(
        prompt=build_policy_prompt(state, state.tactic_history),
        n=n_tactics,
        temperature=0.8
    )

    # 2. Submit one proof-state expansion item.
    #    EnvClient may microbatch this item with other graph searches, but
    #    the tactics for this state remain one backend item / one worker lease.
    results = await env_client.step(
        node_id=state.id,
        state_token=state.state_token,
        tactics=tactics,
        timeout_ms=5000
    )

    # 3. Estimate value of each new state in one batched call
    new_states = [r.new_state for r in results if r.status != "error"]
    values = await model_client.estimate_value(new_states)

    return results, values
```

### 3.4 Hindsight Experience Replay (HER)

A proved internal node is a candidate training root. HER candidates become
A-type data only after context reification, proof rendering, deduplication,
and `/exec/verify` (§2.7, path C) under the same env_profile.

The proof is represented as a `TacticNode` tree (see concern G3). HER
candidates are extracted by iterating all proved subtree roots in the tree.
Each proved subtree has its own `rendered_lean` reconstructed from tactic
history and is re-verified independently by Kimina before entering training.

Track two multipliers separately:

```
her_candidate_multiplier = candidate_subproofs / verified_root_proofs
her_verified_multiplier  = verified_subproofs  / verified_root_proofs
```

The gap between these is a key diagnostic (see concern R2). Candidates that
fail re-verification — typically because they reference outer local context
not present when run as standalone roots — are discarded silently.

```python
def extract_all_subproof_candidates(proof_tree: TacticNode) -> list[TrainingSample]:
    candidates = []
    for node in iter_proved_subtree_roots(proof_tree):
        candidates.append(TrainingSample(
            root_state=node.state,
            tactic_tree=node,                         # TacticNode tree, not flat list
            whole_proof=node.render_as_lean_proof(),
            depth=node.depth,
            search_budget_used=node.subtree_tactic_count(),
            requires_reverification=True,
        ))
    return candidates
```

When node-general HER lands, only independently verified HER samples enter
`a_type_data`. Path-A policy/value rows are produced from accepted search steps,
not from whole-proof HER rendering.

### 3.5 Value Function Data

Proved states are positive labels. There are two distinct kinds of negative
labels, which must not be conflated (see concern G2):

**Censored negatives**: states searched but not proved. These are NOT
mathematically false — they are "not found by this policy at this budget."
Train with reduced weight (weight=0.25, subject to ablation — see R3).
Only include states with sufficient search effort (min 50 tactics tried)
to avoid labeling under-explored states as negative.

**Disproved states**: states where the logical negation of the goal was
proved via negation pruning (see G5). These ARE definitively mathematically
false. Train with full weight. Stored with `disproved=TRUE` in the schema.

```python
def extract_value_labels(
    proof_tree: TacticNode,
    failed_nodes: list[FactorizedProofState],
    disproved_nodes: list[FactorizedProofState],
    min_effort: int = 50
) -> list[ValueLabel]:
    labels = []

    # Positive: states on verified paths to proof
    for node in all_proved_nodes(proof_tree):
        labels.append(ValueLabel(
            state=node.state, label=1,
            depth=node.depth, effort=node.total_tactics_tried,
            weight=1.0, disproved=False,
        ))

    # Disproved: negation proved — definitive, full weight
    for node in disproved_nodes:
        labels.append(ValueLabel(
            state=node, label=0,
            weight=1.0, disproved=True,
        ))

    # Censored negative: not solved after sufficient effort
    for node in failed_nodes:
        if node.total_tactics_tried >= min_effort:
            labels.append(ValueLabel(
                state=node, label=0,
                depth=node.depth, effort=node.total_tactics_tried,
                weight=0.25,   # see R3: this weight needs ablation
                disproved=False,
            ))

    return labels
```

### 3.5.1 Negation Pruning (try_negation flag, default False)

> See concern G5. Not yet implemented. Gated per-theorem by provenance, not
> globally: the SearchEngine sets `try_negation` from `TheoremSpec.source` —
> off for known-true targets (`leandojo`/`mathlib`/`minif2f`), on for
> `autoformalized` and speculative-decomposition statements where the goal may
> be genuinely false. Restricted to single-goal states (a Lean state may hold
> multiple goals; `¬P` is a clean action only when there is one).

```python
def should_try_negation(spec: TheoremSpec) -> bool:
    # provenance label already lives in theorems.source (§4.2);
    # TheoremSpec carries it through to the engine.
    return spec.source in {"autoformalized"}   # extend per Extension B / decomposition
```

For each new single-goal state with goal `⊢ P`, a synthetic action is added
to the state's action pool: prove `¬P` (i.e., `P → False`) in the same local
context. This action competes under normal UCB selection alongside all other
candidate tactics. It receives a full sub-search — UCB can select and retry
it across many iterations with different tactic attempts each time.

If the negation is proved, the state is marked DISPROVED. Propagation sends
"dead" upward through all parent AND-nodes containing this state: an AND-node
with any DISPROVED child can never succeed and is eliminated from its parent
OR-node's options. This is the hard-termination complement to soft budget
exhaustion.

```python
async def expand_with_negation(state, model_client, env_client, n_tactics=8):
    # Normal tactic candidates
    tactics = await model_client.sample_tactics(
        prompt=build_policy_prompt(state, state.tactic_history),
        n=n_tactics, temperature=0.8
    )

    # Synthetic negation action: prove ¬P
    neg_tactic = build_negation_tactic(state.goal)   # e.g. "push_neg; ..."
    all_tactics = tactics + [neg_tactic]

    results = await env_client.step(
        node_id=state.id,
        state_token=state.state_token,
        tactics=all_tactics, timeout_ms=5000
    )

    neg_result = results[-1]
    if neg_result.status == "proved":
        return DisprovedException(state)   # propagate DISPROVED upward

    normal_results = results[:-1]
    new_states = [r.new_state for r in normal_results if r.status != "error"]
    values = await model_client.estimate_value(new_states)
    return normal_results, values
```

The DISPROVED state is recorded in `state_value_labels` with `disproved=TRUE`
and `label=0` at full weight. Cost: one extra Kimina step per expansion when
enabled. Benefit: eliminates dead branches immediately rather than exhausting
budget on them.

---

## 3.6 Supported Search Algorithms

LeanFoundry supports multiple search modes behind `SearchEngine` and
`build_engine(config)`. The current code has two implemented wedges:
direct whole-proof search (`DIRECT`, `SELF_CORRECT`) and AND/OR tree search
(`TREE`, with pluggable PUCT and best-first selection strategies). Beam,
optimistic/RMaxTS-style search, graph/MCGS, and richer HER remain future
algorithms until replay/eval shows the simpler baselines are insufficient.
All implemented modes use `EnvBackend` for Lean execution and `PolicyClient`
for model calls; search code does not construct those clients.

### 1. Direct Whole-Proof Sampling

The model samples complete Lean proofs from theorem statements.
LeanFoundry verifies all attempts in batch and reports pass@k.

Use cases: baseline evaluation, whole-proof Expert Iteration, GRPO
rollouts, comparison against Goedel/DeepSeek-style systems.

### 2. Self-Correction Search

The model generates a proof, receives Lean error feedback from Kimina,
and revises for one or more rounds.

Use cases: Goedel-style evaluation, self-correction SFT data generation,
compiler-feedback training traces.

### 3. AND/OR Tree Search With Best-First Selection

LeanFoundry expands the open leaf with the strongest implemented best-first
score: value estimate when present, otherwise `best_first_missing_value_score`,
then fewer open goals, fewer visits, and stable order. It does not currently
combine policy logprob, depth, and novelty.

Use cases: value-model evaluation, search-efficiency baseline, stronger
alternative to fixed-width beam search.

### 4. AND/OR Tree Search With PUCT Selection

PUCT selection scores actions locally under the current root-to-leaf descent.
For split actions, the engine attacks the hardest open child under the selected
action. Value backup uses product over AND children and max over OR actions.

Use cases: tree-search baseline before graph merging is added, policy/value
integration tests, and solved@budget curves.

### 5. Tactic Beam Search (deferred)

Maintain a beam of proof prefixes and keep the best resulting prefixes by a
future scoring rule. Deferred until the direct/tree baselines and eval runners
make the comparison meaningful.

### 6. Optimistic Search / RMaxTS-Style Search (deferred)

Add optimism bonuses for underexplored states or actions. Deferred until the
baseline tree path has durable replay/eval and real trace evidence.

### 7. MCGS: Monte Carlo Graph Search (deferred)

Graph search requires a complete Lean state-identity fingerprint before states
reached by different paths can be merged soundly. Until that gate passes, v0
search is tree search and does not merge states.

### 8. AND/OR MCGS (deferred)

The full Aristotle-style graph algorithm combines OR-over-actions,
AND-over-subgoals, graph merging, hardest-child prioritization, HER, and value
labels. LeanFoundry keeps this as the north-star reference, not the current
implemented contract.

---

## 3.7 Search Implementation Roadmap

```
current baseline
  direct whole-proof sampling
  self-correction loop
  AND/OR tree search with PUCT selection
  AND/OR tree search with best-first selection
  Path-A policy/value extraction and SQLite replay store

next core work
  env-profile ingress policy
  eval runners and benchmark/env-profile manifests
  policy history/comment API contract
  DISPROVED semantics before enabling try_negation

later algorithms
  tactic beam search
  optimistic / RMaxTS-style search
  validated MCGS state merging
  AND/OR MCGS with node-general HER
```

---

## 4. Data Stores

### 4.1 A-Type Data (Theorem + Verified Proof)

Used for whole-proof SFT artifacts. A row enters this table only when a
complete rendered proof passed final `/exec/verify` in a known `env_profile`.
Path-A per-state policy/value rows do not require a whole-proof render and are
stored separately.

```sql
CREATE TABLE a_type_data (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT NOT NULL REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  header TEXT NOT NULL,
  lean_proof TEXT NOT NULL,
  proof_hash TEXT NOT NULL,
  verified_by_backend BOOLEAN NOT NULL DEFAULT TRUE,
  proof_type TEXT,
  tactic_sequence TEXT,
  correction_input TEXT,
  source TEXT NOT NULL,
  model_version INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 B-Type Data (Theorem Statement Only, No Proof)

Used for Expert Iteration and GRPO. The model finds the proof.

```sql
CREATE TABLE theorems (
  id TEXT PRIMARY KEY NOT NULL,
  lean_statement TEXT NOT NULL CHECK (length(lean_statement) >= 1),
  informal_statement TEXT,
  env_profile TEXT NOT NULL CHECK (length(env_profile) >= 1),
  header TEXT NOT NULL,
  initial_lean_block TEXT,
  difficulty_estimate REAL,
  pass_rate_current REAL,
  pass_rate_updated_at TIMESTAMP,
  source TEXT NOT NULL DEFAULT 'unknown' CHECK (length(source) >= 1),
  split TEXT NOT NULL DEFAULT 'train',
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

`source` is the provenance label propagated into `TheoremSpec.source`; it is
the future gate for `try_negation` (§3.5.1).

### 4.3 Trajectories (Replay Buffer)

```sql
CREATE TABLE trajectories (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT NOT NULL REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_type TEXT NOT NULL,
  whole_proof TEXT,
  tactic_sequence TEXT,
  search_budget_used INTEGER,
  is_subproof BOOLEAN NOT NULL DEFAULT FALSE,
  parent_trajectory_id TEXT,
  model_version INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

`tactic_sequence` stores serialized `ProofTree` JSON for the solved projection,
not the live AND/OR runtime tree. `whole_proof` is nullable because Path-A
attempts can emit per-state training data even when Path-B rendering or final
verification fails.

Positive Path-A policy rows are stored separately:

```sql
CREATE TABLE policy_examples (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_state_hash TEXT NOT NULL,
  proof_state_pretty TEXT,
  proof_prefix TEXT NOT NULL DEFAULT '',
  tactic TEXT NOT NULL,
  depth INTEGER NOT NULL CHECK (depth >= 0),
  model_version INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Value labels use the same replay provenance:

```sql
CREATE TABLE state_value_labels (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_state_hash TEXT NOT NULL,
  proof_state_pretty TEXT,
  label INTEGER NOT NULL CHECK (label IN (0, 1)),
  weight REAL NOT NULL DEFAULT 1.0 CHECK (weight >= 0),
  disproved BOOLEAN NOT NULL DEFAULT FALSE,
  depth INTEGER CHECK (depth IS NULL OR depth >= 0),
  tactics_tried_on_subtree INTEGER CHECK (
    tactics_tried_on_subtree IS NULL OR tactics_tried_on_subtree >= 0
  ),
  model_version INTEGER NOT NULL,
  CHECK (NOT disproved OR (label = 0 AND weight = 1.0))
);
```

`disproved=TRUE` is reserved for future semantic falsity certificates such as
negation pruning. `label=0, disproved=FALSE` is a censored negative and carries
a reduced `weight`.

### 4.4 Formalizer Output (B-Type Statements from Extension B)

When Extension B is active, autoformalized statements land here first
and require additional vetting before entering the main theorems table:

```sql
CREATE TABLE formal_statements_staging (
  id TEXT PRIMARY KEY NOT NULL,
  informal_source TEXT,
  informal_statement TEXT,
  lean_statement TEXT NOT NULL,
  env_profile TEXT NOT NULL,
  formalizer_version TEXT,
  semantic_judge_score REAL CHECK (
    semantic_judge_score IS NULL
    OR (semantic_judge_score >= 0 AND semantic_judge_score <= 1)
  ),
  syntax_checked BOOLEAN NOT NULL DEFAULT FALSE,
  dedup_hash TEXT,
  promoted_to_theorems BOOLEAN NOT NULL DEFAULT FALSE
);
```

---

# Part II: Training Recipe

---

## 5. Hardware Configuration

### 5.1 Machine Spec

```
GPUs:  8x H100 80GB SXM
CPUs:  512 cores (verify NUMA topology before allocating workers)
RAM:   1-2TB (verify before setting worker_pool_size)
Disk:  4TB NVMe SSD
```

**Env Backend worker sizing:**

Worker count is empirical, not derived from CPU count alone. Kimina uses
multiple Lean REPL worker processes and LRU header/import reuse. Public
references support import/header reuse and process pooling, not a guarantee
that Mathlib RSS is loaded once and shared across hundreds of workers.

Phase -1 therefore includes RSS/PSS and latency sweeps at 64, 128, 256,
and 400 workers for lightweight REPL verification, but Pantograph/mathlib
tactic stepping must use a separate smaller sweep. Initial profiling with
`Mathlib.Data.Finset.Card` + `Mathlib.Data.Nat.Basic` showed roughly 1.3GB RSS
per warm Pantograph worker on macOS, so practical single-node pools are likely
in the 4-32 worker range depending on RAM and imports. The selected
`worker_pool_size` is the largest stable point with acceptable queue latency,
no restart storm, and enough RAM headroom.

```yaml
kimina_worker_rss_sweep:
  worker_counts: [4, 8, 16, 32]
  headers:
    - "import Mathlib\nimport Aesop"
  workload:
    proof_mix: [verify, init_state_token, step_state_token, extract_trace]
    duration_minutes: 30
  metrics:
    - total_rss_gb
    - total_pss_gb_if_available
    - per_worker_rss_p50_p95_max
    - startup_prewarm_time
    - header_cache_hit_rate
    - step_sec
    - queue_wait_p50_p95
    - tactic_latency_p50_p95
    - restart_count
    - oom_count
    - disk_cache_pressure
    - numa_imbalance
```

Pin each worker group to its local NUMA node after the sweep. Cross-NUMA
memory access can degrade Lean process latency. Verify the actual topology
with `numactl --hardware` before configuring affinity.

### 5.2 Base Model: Qwen3.6-27B

**Why Qwen3.6-27B specifically:**

Qwen3.6-27B is the latest open-weight dense model from the Qwen family
(released April 2026, Apache 2.0). Key properties:
- 27B parameters (dense, not MoE)
- Long-context capable, but LeanFoundry does not assume 262K rollout context
- Native thinking mode: may generate `<think>...</think>` before output
- SGLang/vLLM/Transformers-compatible
- Not Lean-specialized, so improvements are attributable to our framework

**Serving contract for LeanFoundry:**

```
- Serve Qwen3.6-27B in text-only mode for Lean tasks.
- Initial rollout/search context buckets: 8K / 16K / 32K.
- Do not depend on 262K context for routine search.
- Tactic prediction disables thinking by default.
- Whole-proof and self-correction may allow thinking, but only extracted Lean
  code is sent to the verifier.
- Any `<think>` leakage inside Lean code is stripped or rejected.
```

**Why dense over MoE (Qwen3.6-35B-A3B):**

Dense 27B is the v0 default for engineering simplicity and clean attribution.
MoE is not rejected on principle. With Expert Parallelism, expert parameters
and optimizer state are sharded across GPUs, so the memory profile differs
substantially from the naive "total parameters" argument. MoE requires a
separate EP-aware fit, throughput, weight-sync, and routing stability profile
before adoption. MoE is a v0.2 optimization candidate after the dense path
is profiled and stable.

**Why not start from DeepSeek-Prover or Goedel-Prover:**

Starting from an already-specialized prover checkpoint makes the framework's
contribution harder to attribute. Use them as teachers (to generate SFT
data) and baselines (to compare against), not as the main actor's starting
point.

**GPU allocation (baseline, subject to profiling):**

The 6/2 Megatron/SGLang split is an initial profiling baseline, not a
settled architecture. Full 27B fine-tuning is state-memory constrained:
BF16 weights + FP32 gradients + FP32 optimizer states ≈ 18 bytes per
parameter. At 27B on 6 training GPUs (TP=2, PP=3, DP=1), this is
approximately 81GB per GPU before activations — likely not feasible
without relief.

The likely concrete allocation after profiling is 8 GPUs for training
updates (TP=4, PP=2 or TP=2, PP=4), with phase-separated rollout/search
and update cycles for EI and search-based EI stages. The 6/2 co-located layout
is tested for GRPO only if the fit gate passes with margin.

```
Initial profiling baseline:
  Training (Megatron):  GPU 0-5  (6 cards), TP=2, PP=3
  Inference (SGLang):   GPU 6-7  (2 cards), TP=2

Likely post-profiling layout:
  Training updates:     all 8 GPUs, TP=4, PP=2 or TP=2, PP=4
  Rollout/search phase: 2-4 GPUs + Env Backend on CPU
  (phase-separated, not concurrent)

CPU allocation (512 cores):
  Env Backend pool:     profiled_worker_pool_size (NUMA-pinned, see 5.1)
  Search Engine:        32 cores (asyncio, NUMA 0)
  Data Buffer:          4 cores  (SQLite server, NUMA 3)
  OS/misc:              remaining cores
```

---

### 5.3 Phase -1: Systems Fit and Throughput Profiling

No full training begins until this phase completes and produces a
`resource_profile_manifest.json` for every stage.

#### Required gates

```
Gate A: model-load-only
  Load model shards. Build optimizer. Allocate grad buffers. No forward.
  Pass if peak_reserved < 68GB on every rank.

Gate B: forward-only
  seq_len = p95 length bucket from the format length audit (below).
  micro_batch = 1.
  Pass if peak_reserved < 72GB.

Gate C: full update
  forward + backward + optimizer step, 10 measured steps.
  Pass if peak_reserved < 74GB and no rank grows across steps.

Gate D: long-run stability
  100 steps on the selected config.
  Pass if memory growth < 1GB and no OOM.

Gate E: Env Backend worker sweep
  Run 64/128/256/400 worker RSS/PSS and latency sweep from 5.1.
  Pass when selected worker_pool_size has stable RSS, acceptable queue_wait_p95,
  and no restart/OOM storm.
```

#### Format length audit (run before memory profiling)

```python
def build_length_report(dataset, tokenizer):
    rows = []
    for sample in dataset:
        prompt_len = len(tokenizer.encode(sample["prompt"]))
        target_len = len(tokenizer.encode(sample["target"]))
        rows.append({
            "format": sample["format"],
            "source": sample["source"],
            "prompt_len": prompt_len,
            "target_len": target_len,
            "total_len": prompt_len + target_len,
        })
    return percentile_table(rows, by=["format", "source"],
                            percentiles=[50, 75, 90, 95, 99, 100])
```

Report p50/p75/p90/p95/p99/max for each format (whole_proof, tactic,
self_correction, value, grpo). Use p95 as the default seq_len for dry
runs; route p99 examples to special long-context microbatch=1 runs.

#### Memory dry-run matrix

```yaml
memory_dry_run:
  seq_lens: [4096, 8192, 16384, 32768]
  micro_batch_sizes: [1, 2]
  parallelism:
    - {gpus: 6, tp: 2, pp: 3}
    - {gpus: 8, tp: 4, pp: 2}
    - {gpus: 8, tp: 2, pp: 4}
  recompute: [none, selective, full]
  sequence_parallel: [true]
  stages:
    - stage1_sft_whole_proof
    - stage1_sft_tactic_policy
    - stage1_sft_self_correction
    - stage3_search_tactic_policy
    - stage3_value_training
    - stage4_grpo_whole_proof
    - stage4_grpo_self_correction
```

Instrumentation:

```python
import torch, time, json, os

def log_rank_memory(tag, step, path="memory_profile.jsonl"):
    torch.cuda.synchronize()
    row = {
        "tag": tag, "step": step,
        "rank": int(os.environ.get("RANK", -1)),
        "allocated_gb": torch.cuda.max_memory_allocated() / 1024**3,
        "reserved_gb": torch.cuda.max_memory_reserved() / 1024**3,
        "timestamp": time.time(),
    }
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")
```

Wrap training phases with NVTX ranges for CPU/GPU idle analysis in
Nsight Systems.

#### Resource profile manifest

Gate C produces a mandatory manifest before Stage 1 begins:

```json
{
  "model": "qwen3.6-27b",
  "env_profile": "lean4_mathlib_pinned",
  "stage": "stage1_sft",
  "parallelism": {"gpus": 8, "tp": 4, "pp": 2},
  "seq_len": 16384,
  "micro_batch": 1,
  "recompute": "selective",
  "sequence_parallel": true,
  "peak_reserved_gb_max_rank": null,
  "tokens_per_sec": null,
  "mfu": null,
  "worker_pool_size": null,
  "kimina_step_sec": null,
  "kimina_queue_wait_p95_ms": null,
  "oom": null,
  "notes": "fill after profiling run"
}
```

#### Memory pressure response ladder

Ordered from least to most capability loss. Try earlier tiers first.

```
Tier 0: no capability loss
  1. Use all 8 GPUs for training updates (phase-separated EI).
  2. Sweep TP/PP: try TP=4 PP=2 and TP=2 PP=4.
  3. Enable sequence parallelism with TP.
  4. Length bucketing + packed batches.
  5. Activation checkpointing (selective then full).
  6. Recompute logprobs in GRPO instead of storing rollout tensors.
  7. Store rollouts on CPU, load per microbatch.

Tier 1: low risk, verify by ablation
  8. Route p99 long examples to separate long-context microbatch=1 runs.
  9. For tactic-policy samples, use current proof state + local context,
     not full theorem history when depth is large.

Tier 2: medium risk
  10. CPU-offload optimizer states if the Slime/Megatron path supports it.
  11. FP8 training after loss/eval ablation.

Tier 3: last resort
  12. LoRA/QLoRA-only for v0 demo.
  13. Smaller dense model.
```

Context parallelism (CP) is a candidate for long sequences but competes
with TP/PP for GPU resources on a single 8-GPU node. Only consider CP
after the model-state fit is resolved.

---

### 5.4 Slime Integration

Slime (THUDM) is the intended online RL orchestrator for the training repo
because it provides Megatron-LM + SGLang integration, weight synchronization,
and a custom rollout interface. It is **not** part of the LeanFoundry core
execution path. The dependency is available only through the CI-excluded
`training` optional extra, and the in-repo `SlimeAdapter` remains a placeholder
until a pinned Slime commit and compatibility tests are chosen.

The source-level integration shape is pull, not push. Slime loads a rollout
function and calls it each rollout iteration; LeanFoundry does not stream
samples into Slime's buffer through `RLEngineBase.submit_samples(...)`. The
clean hook for theorem proving is the full rollout function:

```text
--rollout-function-path training_repo.rollouts.lean_rollout.generate_rollout
```

The per-sample hook `--custom-generate-function-path` is useful for linear
agent episodes (tool call -> observation -> next model call). It is not the
right default for graph proof search because Slime's default rollout launches
`n_samples_per_prompt` samples independently. Mapping one tactic candidate to
one `Sample` would recreate the forbidden flattening problem. Mapping one full
theorem search to one `Sample` is possible for a prototype, but it makes env
batching across proof graphs and trajectory extraction awkward.

That function returns `list[list[Sample]]` groups to Slime. LeanFoundry's role
inside it is algorithm-neutral search and optional durable side-write to the
SQLite `ReplayStore`; Slime owns the online data buffer and trainer. The full
rollout function owns the theorem-search orchestration:

```python
# training_repo/rollouts/lean_rollout.py
from leanfoundry.env_backend import make_env_backend
from leanfoundry.proofsearch import SearchConfig, run_search_batch
from training_repo.policy import SlimePolicyClient
from training_repo.samples import samples_from_search_results

async def generate_rollout(args, rollout_id, data_buffer, evaluation=False):
    theorem_groups = data_buffer.get_samples(args.rollout_batch_size)

    env = await make_env_backend(args.env_backend_config)
    policy = SlimePolicyClient(args)
    search_cfg = SearchConfig.from_args(args)

    search_results = await run_search_batch(
        theorem_groups=theorem_groups,
        policy=policy,
        env=env,
        config=search_cfg,
        evaluation=evaluation,
    )

    samples = samples_from_search_results(search_results)
    return samples
```

`Sample` can represent either Path-A formulation: one Markovian row per node
(`prompt=state`, `response=tactic`) or a history-conditional trajectory where
the prompt includes `proof_prefix` and the loss mask trains only model-authored
tactic spans. Grouping for EI vs GRPO is a training-side decision; core
extraction keeps emitting algorithm-neutral `TrainingArtifacts`.

---

## 6. Data for Each Stage

### Training Pipeline Overview

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  Phase -1: fit and throughput profiling                         │
  │  resource_profile_manifest.json required before any SFT begins  │
  └────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Stage 1: Cold-start SFT                                        │
  │                                                                 │
  │  Data Buffer (A-type) ──► Trainer                               │
  │  Sources: LeanDojo train split + reverified external A-type      │
  │  Three formats: whole_proof | tactic_prefix | self_correction   │
  └────────────────────────────┬────────────────────────────────────┘
                               │ checkpoint v1
                               ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Stage 2: Whole-proof Expert Iteration                          │
  │                                                                 │
  │  B-type train theorems ──► Inference Engine (sample N proofs)   │
  │       ──► Env Backend /exec/verify ──► pass-rate bucketing      │
  │                                                                 │
  │       pass_rate = 0        → Stage 3 queue                      │
  │       0 < pass_rate ≤ 0.75 → active EI → A-type                 │
  │       pass_rate > 0.75     → deprioritize                       │
  │                                                                 │
  │  New A-type → Data Buffer → Trainer (SFT) → checkpoint v2       │
  └────────────────────────────┬────────────────────────────────────┘
                               │ checkpoint v2
                               ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Stage 3: Search-based Expert Iteration                         │
  │                                                                 │
  │  B-type (pass_rate=0) ──► Search Engine                         │
  │       ├── PolicyClient → Inference Engine (sample_tactics)      │
  │       ├── /exec/step_batch → Env Backend (tactic execution)     │
  │       └── Path-A extraction → policy/value rows + replay        │
  │                                                                 │
  │  Policy/value rows → Trainer; verified whole proofs → A-type    │
  └────────────────────────────┬────────────────────────────────────┘
                               │ checkpoint v3
                               ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Stage 4: GRPO                                                  │
  │                                                                 │
  │  B-type (0 < pass_rate ≤ 0.75) ──► LeanRollout                  │
  │       ├── Inference Engine: sample G proofs per theorem         │
  │       └── Env Backend /exec/verify: binary reward               │
  │                                                                 │
  │  (theorem, rollouts, rewards) → Trainer (GRPO)                  │
  │  Multi-task: whole-proof + self-correction                      │
  │  KL penalty against reference ──► checkpoint v4                 │
  └─────────────────────────────────────────────────────────────────┘
```

Autoformalization is **not** part of the core Stage 1–4 loop. Extension B
begins only after the LeanDojo-based core pipeline is stable and eval leakage
rules are locked. Until then, any external formal data must be reverified under
our env_profile and pass contamination filtering before entering training.

### The A/B Distinction

```
A-type data = theorem + verified proof  → used for SFT
B-type data = theorem statement only    → used for EI, search, GRPO

The training pipeline converts B into A:
  search finds a proof for a B-type theorem
  Env Backend /exec/verify accepts the rendered whole proof
  the (theorem, proof) pair becomes A-type data
  → added to replay buffer for future SFT rounds
```

### Stage 1 Data (A-type)

```
Primary:
  LeanDojo (state, tactic) pairs             ~220k tactic samples
  Mathlib proofs via Kimina infotree         ~100k theorems

Optional training-repo warm-start source:
  LeanTree factorized proof-tree dataset, if selected by training repo
    - tactic-policy SFT from factorized states and next tactic edges
    - value/critic warm-start from proof_depth/proof_size
    - validation traces replayed through Env Backend before use

Supplementary (re-verify under our env_profile before use):
  Goedel-Prover SFT data (1.79M samples)    best available A-type source
  DeepSeek-Prover-V1 proof data              large, diverse

Self-correction examples:
  Generate via teacher model (Goedel-Prover-V2-8B or similar):
    1. Sample failed proof attempts for known theorems
    2. Run Kimina, collect Lean error messages
    3. Ask teacher to produce corrected proof
    4. Env Backend /exec/verify accepts corrected proof
    5. (statement, failed_proof, errors, corrected_proof) is one sample

NOTE: any data not verified under our env_profile must be re-verified.
Mathlib version mismatches silently corrupt training data.
```

### Stage 2 Data (B-type, whole-proof EI)

```
Core training pool:
  LeanDojo train split theorems
  Optional external formal statements only if:
    - env_profile verification passes
    - theorem/proof overlap with eval splits is removed
    - split assignment is fixed before training

Eval-only by default:
  miniF2F test
  PutnamBench
  MathOlympiadBench

Do not use eval-only benchmarks for training, pass-rate bucketing,
prompt tuning, checkpoint selection, or curriculum construction.

Pass rate bucketing (updated each iteration):
  pass_rate = 0           → send to search queue (Stage 3 input)
  0 < pass_rate <= 0.75   → active training set for this stage
  pass_rate > 0.75        → deprioritize (mostly learned)

Quick-sampling for difficulty estimation:
  n=16 proofs, budget set by resource_profile_manifest
  Runs at start of each EI iteration to update pass_rate_current
```

### Stage 3 Data (B-type, Search-Based EI)

```
Input: Stage 2's pass_rate = 0 theorem pool
  + any B-type theorems from Extension B (when active)

Current Path-A output:
  proved tactic edge        → policy_examples row (state + proof_prefix + tactic)
  explored state            → value label when label-emission mode owns it
  rendered+verified proof   → optional whole_proof A-type sample
  attempt                   → trajectory + replay diagnostics

Deferred output:
  each verified proved subtree → HER subproof sample (subproof=TRUE)
  node-general DISPROVED labels → full-weight value negatives
```

### Stage 4 Data (B-type, GRPO)

```
Filtered subset of all B-type theorems:
  current whole-proof pass_rate in [0.05, 0.75]
  prefer [0.10, 0.50] for strongest signal

Multi-task RL (following Goedel-V2 recipe):
  50% whole-proof generation tasks
  50% self-correction tasks (statement + failed proof + errors → corrected)
  batch size: 128
  n rollouts per prompt: 8
  dynamic filtering: remove prompts where all 8 rollouts succeed or all fail

Structure consistency reward (optional, from DeepSeek-Prover-V2):
  If model planned a subgoal decomposition but proof skips lemmas: -0.5
  Encourages proof structure faithfulness
```

---

## 7. Training Pipeline

### Stage 1: Cold-Start SFT

**Purpose**: teach the model Lean 4 syntax, basic tactic usage, and
proof structure. Do NOT expect it to "know how to prove" after this —
just learn the format.

Train three formats simultaneously (not sequentially):

**Format 1: Whole-proof generation**
```
Input:  theorem statement
Output: complete Lean proof
```

**Format 2: Tactic/prefix policy**
```
Input:  current proof state + tactic history so far
Output: next tactic
```

**Format 3: Self-correction**
```
Input:  theorem statement + failed proof + Lean error messages
Output: corrected proof
```

Format 3 is important because Goedel-Prover-V2's ablations show compiler
error messages substantially improve the model's ability to revise proofs.
It's also cheap to generate: use a teacher model on known theorems.

Qwen3.6-27B's native thinking mode (`<think>...</think>`) is useful here:
train with CoT in Format 1 and Format 3, where deliberate reasoning
helps. Format 2 (single tactic) does not need CoT.

Training:
```
Standard cross-entropy loss
~3 epochs over the full A-type dataset
No RL at this stage
```

Checkpoint this model. It is the starting point for Stage 2 and the
reference for measuring improvement.

### Stage 2: Whole-Proof Expert Iteration

**Purpose**: on the large pool of B-type theorems, find proofs the model
can discover through direct sampling, and train on them iteratively.

Each iteration:

```
1. Update pass rates
   Quick-sample all active B-type theorems (n=16, 10s budget via SGLang)
   Update pass_rate_current in theorems table

2. Select training set
   Take theorems with 0 < pass_rate <= 0.75
   This is the frontier: model can sometimes prove these, not always

3. Full sampling
   For each frontier theorem: sample n=32 proofs via SGLang
   Send to Env Backend /exec/verify in batch
   Collect all successful proofs

4. Add to A-type data
   For each verified proof: insert into a_type_data with source='search_found'
   HER subproof extraction is deferred to the node-general HER slice

5. Train
   Sample from full replay buffer (all A-type data, old and new)
   SFT on whole-proof and tactic-sequence formats
   One pass over new data, fractional pass over old data

6. Update model in SGLang
   Slime handles weight sync from Megatron to SGLang

7. Collect pass_rate=0 theorems into the search queue for Stage 3
```

Run until frontier theorems are mostly cleared
(pass_rate=0 pool stops growing, frontier shrinks).

### Stage 3: Search-Based Expert Iteration

**Purpose**: find proofs for theorems that whole-proof sampling cannot
reach (pass_rate=0 from Stage 2). This is a training data generator,
not an optional inference enhancement.

Tree search during training finds proof steps and sometimes whole proofs the
model cannot generate directly, then trains the model on Path-A policy/value
artifacts and verified whole-proof artifacts when available. Graph/MCGS and
node-general HER are later upgrades to this loop, not prerequisites for the
baseline.

Each iteration:

```
1. Take theorems from the search queue (Stage 2's pass_rate=0 pool)

2. Run tree search for each theorem
   Budget: 500 tactics per theorem
   Use Env Backend /exec/step_batch with Pantograph state_tokens
   Simultaneously:
     policy calls  → SGLang (sample 8 tactics per state)
     value calls   → SGLang (estimate proof probability per state)
     tactic exec   → Env Backend

3. Collect training data from search
   Proved tactic edges: insert into policy_examples
   State labels: insert into state_value_labels when label mode owns them
   Successful rendered+verified proofs: optional whole_proof A-type sample
   HER subproofs: deferred until node-general extraction lands

4. Train
   Policy loss:       cross-entropy on Path-A policy examples
   Value loss:        binary cross-entropy on state_value_labels
   Whole-proof loss:  cross-entropy on successful proof strings
   Combined: policy_loss + value_loss * 0.5

5. Update model (Slime weight sync)

6. Re-attempt theorems that search just succeeded on with whole-proof
   sampling — some may now be achievable directly (useful for Stage 4)
```

Model averaging (after each search-training phase):
If whole-proof pass@32 improves but pass@1 drops, or if search proof
discovery rate per Lean call decreases, try:
```
θ_avg = α * θ_search + (1-α) * θ_pre_search,  α ∈ {0.5, 0.7, 0.9}
Select by: search proofs found per 10k Lean calls
```
Use averaging to preserve expansion diversity, not as a default step.

### Stage 4: GRPO

**Purpose**: once search has found proofs and trained the model on them,
use online RL to sharpen the model's direct generation ability on
theorems where it now has a nonzero success rate.

GRPO should NEVER run on theorems where the whole-proof pass rate is 0.
The GRPO signal requires nonzero reward. The correct sequence is:

```
Search finds proof for theorem T (Stage 3)
    ↓
SFT on that proof trains the model (Stage 3)
    ↓
Model now has nonzero pass rate on theorems related to T
    ↓
GRPO can now improve performance on those theorems (Stage 4)
```

GRPO loop:

```python
for batch in frontier_theorems(pass_rate_range=(0.05, 0.75)):
    # Sample G=8 whole proofs per theorem
    proofs = sglang.generate(batch, n=8, temperature=0.9)

    # Verify all through /exec/verify
    rewards = env_backend.verify_batch(batch, proofs)

    # GRPO objective
    advantages = group_normalize(rewards)  # per-theorem normalization
    policy_loss = -sum(advantages * log_probs(proofs))

    # KL penalty to prevent reward hacking
    kl_penalty = beta * KL(current_policy || reference_policy)
    loss = policy_loss + kl_penalty

    # Multi-task: interleave with self-correction task
    # (50% whole-proof, 50% self-correction, per Goedel-V2)

    loss.backward()
    optimizer.step()
    slime.sync_weights_to_sglang()
```

Reward hacking guard:
```
Reject proof-search tactics that contain:
  sorry / admit tokens

Reject final whole-proof artifacts that contain:
  sorry / sorryAx
  unauthorized axioms not in the approved Mathlib axiom set
  unsafe proof escapes (e.g. unsafeEval, Lean.ofScientific abuse)
  wrong env_profile (proof verified on different Mathlib commit)

Do NOT reject noncomputable:
  Many legitimate classical Mathlib proofs involve noncomputable
  definitions. Rejecting noncomputable discards valid mathematics.
```

### Training Stage Exit Criteria

Calendar estimates are intentionally deferred until Phase -1 produces measured
throughput, sequence-length distributions, memory headroom, rollout rate, Lean
step/sec, verified proofs/hour, and weight-sync overhead.

```
Phase -1 exits when:
  resource_profile_manifest.json exists for SFT, whole-proof EI,
  search-based EI, and GRPO.

Stage 1 exits when:
  SFT improves Lean syntax validity, valid tactic rate, direct pass@k,
  and self-correction success over the base model.

Stage 2 exits when:
  whole-proof EI frontier stabilizes or marginal verified proofs/hour drops
  below the configured threshold for two consecutive iterations.

Stage 3 exits when:
  search proofs_per_10k_calls plateaus across two iterations, or the
  pass_rate=0 queue stops yielding verified proofs under the current budget.

Stage 4 runs only when:
  target theorem buckets have nonzero pass rate and GRPO memory fit passes.

Cycle:
  checkpoint v4 becomes the candidate starting point for the next EI cycle
  only if held-out evals and solved@budget curves improve without contamination.
```

---

## 8. Key Metrics

```
Search quality:
  proof_success_rate          % of theorems proved per EI iteration
  search_proofs_per_10k_calls efficiency of tree/search execution
  replay_buffer_size          total verified proofs in A-type store
  value_function_auc          AUC on state_value_labels held-out set
  her_candidate_multiplier    candidate HER samples / verified root proofs
  her_verified_multiplier     verified HER samples / verified root proofs

Training metrics (W&B):
  pass_at_1                   direct generation success rate
  pass_at_32                  sampling-based success rate
  grpo_reward_mean            average reward per GRPO batch
  frontier_size               theorems in 0 < pass_rate <= 0.75 range

Infrastructure metrics:
  kimina_cache_hit_rate        should be > 0.90
  kimina_worker_utilization    should be > 0.70 during search
  tactic_latency_p50/p95       Kimina execution time
  weight_sync_time             Megatron→SGLang sync duration
  gpu_utilization              > 0.80 during training phase

Evaluation benchmarks:
  miniF2F test split (pass@1, pass@32)
  LeanDojo novel_premises split (primary: hardest split)
  PutnamBench (after Stage 3, aspirational)
```

---

## 8.5 Evaluation Protocol

### Eval ownership boundary

Evaluation splits across the two repos along the same line as everything
else: LeanFoundry eval measures what the infrastructure does given a fixed
model. Training repo eval measures how the model improves across training
iterations. These are different questions and must not be conflated.

```
LeanFoundry eval (infra repo owns):
  solved@budget curves — given a fixed model and fixed search algorithm,
    how many theorems are proved as tactic budget increases?
  proofs per 10k Lean calls — search efficiency across algorithm variants
  Search compute curves — state-token load/tactic/save latency, cache hit rates
  Search algorithm comparisons — direct vs tree PUCT vs tree best-first now;
    beam/MCGS variants later, all run against the same model checkpoint
  Infra throughput metrics — Kimina step/sec, queue wait, worker utilization
  Benchmark loaders, Kimina verification, eval artifact schemas

Training repo eval (training repo owns):
  pass@k progression across checkpoints
  Frontier bucket evolution per EI round
  Data flywheel curves — cumulative verified proofs, HER multiplier
  Benchmark comparison against external systems
  Checkpoint selection decisions
```

The training repo calls LeanFoundry's eval runners with a model endpoint
and receives structured artifact manifests. It never implements Lean
verification or search execution. The infra repo never imports checkpoints
or knows about training stages — it receives a PolicyClient endpoint and
a benchmark spec and produces eval artifacts.

Every eval run writes an artifact manifest:

```json
{
  "run_id": "eval_2026_05_05_model_v2",
  "infra_git_sha": "9a31...",
  "training_git_sha": "c81d...",
  "model_checkpoint": "model_v2",
  "env_profile": "lean4.29.1_mathlib_5e932f97",
  "benchmark": "miniF2F-test",
  "benchmark_commit": "...",
  "mode": "direct",
  "k_values": [1, 2, 4, 8, 16, 32, 64, 128],
  "sampling": {
    "temperature": 0.8,
    "top_p": 0.95,
    "max_tokens": 32768
  }
}
```

### Evaluation Modes

Four modes, not one:

```
1. direct
   theorem statement → whole proof, no feedback
   metric: pass@k (k = 1, 2, 4, 8, 16, 32, 64, 128)

2. self_correct
   initial proof attempt → Kimina errors → revision, 1-2 rounds
   metric: pass@k and pass@k per revision count

3. mcts_state_token
   Kimina/Pantograph state-token backend, stateless at the API level,
   load-balanced across proof-state expansion items
   metric: solved@budget, proofs per 10k Lean calls, latency breakdown
   (queue vs goal_load vs tactics loop vs goal_save)
```

### Benchmark Suite

```
Primary dev eval (used during training to guide decisions):
  LeanDojo novel_premises validation split

Primary final eval (reported in releases):
  LeanDojo novel_premises test split
  miniF2F test split

Secondary final eval (aspirational, add as system matures):
  ProofNet (if compatible with our env_profile)
  PutnamBench (after Stage 3 search-based training)
  MathOlympiadBench (360 olympiad problems, Goedel-V2 released)
    → eval-only, never training data
    → re-verify all statements under our env_profile before use
```

Goedel-V2 reference numbers for comparison:
- miniF2F test: 84.6% pass@32 (8B), 88.1% pass@32 (32B standard),
  90.4% pass@32 (32B self-correction)
- PutnamBench: 86 problems at pass@184

When comparing to Goedel-V2 numbers, note whether env_profiles match.
Their repo uses mathlib4 @ 2f65ba7 under Lean 4.9. If our env_profile
differs, label comparisons as "different verifier environment."

### Pass@k Protocol

Generate K_max samples once per theorem, compute all pass@k from the
same pool. Never regenerate for different k values.

```
K_max = 128  for routine eval
K_max = 1024 for expensive final scaling runs only

Report k = 1, 2, 4, 8, 16, 32, 64, 128
```

For each theorem, solved at k = any(verified[i] for i in range(k)).

When K_max > k, use unbiased estimator:

```python
# n = total samples, c = verified successes
pass_at_k = 1 - comb(n - c, k) / comb(n, k)
```

### Search Compute Curves

For tree/search evaluation, pass@k is the wrong primary metric. Search uses
Lean tactic calls as the budget, not proof samples. Report:

```
Budgets: 50, 100, 250, 500, 1000, 2000 tactic calls

Metrics:
  solved@budget             % theorems proved within budget
  proofs_per_10k_calls      search efficiency
  median_calls_per_solved   cost of a successful proof
  valid_tactic_rate         % tactics accepted by Lean (not error)
  unique_state_rate         state diversity in search tree
  average_proof_depth       depth of found proofs
  value_auc                 how well value function ranks states
  value_calibration_ece     calibration error of value estimates
```

These measure whether training-time search is genuinely improving search
efficiency, which is the core infrastructure claim of this project.

### Progression Curves

LeanFoundry (infra repo) produces and owns:

```
Curve 3: search solved% vs tactic budget
  x = budget (tactic calls), y = solved %
  one line per checkpoint (isolates search infrastructure contribution)

Curve 6: infra throughput
  x = time
  y = Kimina step/sec, cache hit rate, worker utilization, queue wait p95
```

Training repo produces and owns (consuming infra eval artifact manifests):

```
Curve 1: pass@1 and pass@32 across checkpoints
  x = training stage (base → SFT → whole-EI → search-EI → GRPO)
  y = miniF2F test pass rate

Curve 2: pass@k scaling per checkpoint
  x = k, y = benchmark success rate
  one line per checkpoint

Curve 4: frontier bucket evolution
  x = EI iteration
  y = count of theorems in:
      pass_rate = 0 (search queue)
      0 < pass_rate <= 0.75 (active frontier)
      pass_rate > 0.75 (learned)

Curve 5: data flywheel
  x = EI iteration
  y = cumulative verified proofs, search-found proofs, HER multiplier
```

### Evaluation Contamination Rules

1. miniF2F test, PutnamBench, MathOlympiadBench are never used for
   training, pass-rate bucketing, prompt tuning, or checkpoint selection.

2. miniF2F validation may be used during development, but all reported
   numbers must be test-only.

3. Any theorem whose proof appears in A-type training data is removed
   from held-out evaluation sets.

4. Autoformalized statements may be used for training but not for clean
   evaluation unless human-verified and assigned to a fixed eval split
   before any training begins.

5. All benchmark statements are re-verified under the exact eval
   env_profile before evaluation. Do not assume benchmark proofs are
   valid under our Mathlib commit.

---

## 9. Known Risks

**Risk: env_profile contamination**
External data (Goedel, DeepSeek proofs) verified on different Mathlib
commit. Silently produces training samples with invalid proofs.
Mitigation: mandatory Kimina re-verification of ALL external A-type data
under our env_profile before insertion. Reject without re-verification.

**Risk: Search finds only trivial proofs**
Replay buffer fills with easy Path-A examples or future verified HER subproofs.
Model learns to prove easy lemmas and stops improving on harder ones.
Mitigation: track proof complexity (search_budget_used). Filter out
trajectories with budget_used < 5 from tactic-policy training.
Use pass_rate bucketing to avoid overtraining on easy theorems.

**Risk: GRPO reward hacking**
Model finds proofs with sorry or unauthorized axioms.
Mitigation: sorry/admit is rejected at expansion attach-time, and final
`/exec/verify` rejects degenerate whole-proof artifacts.
Reference policy KL penalty prevents policy collapse.

**Risk: Weight sync stalls**
Megatron→SGLang sync takes too long, GPU idle during sync.
Mitigation: overlap sync with trajectory processing. During the ~10-30s
sync window, search can extract Path-A rows, compute state hashes, and write to
SQLite. Future HER extraction can use the same window. True idle time should be
< 5s.

**Risk: Env Backend worker pool exhausted**
The profiled worker pool saturates and new tactic calls queue beyond the p95
threshold.
Mitigation: monitor queue_wait_p95 and worker RSS. If queue_wait_p95 is
consistently > 200ms, reduce search parallelism, increase worker_pool_size if
RSS headroom allows, or move to Extension A scale-out.

**Risk: MCTS tree memory overflow**
Long search trees for hard theorems exhaust RAM.
Mitigation: max tree size of 10k nodes. When exceeded, prune states
with visit_count=1 and low value_estimate. Serialize pruned subtrees
to disk if needed.

**Risk: Later SFT/RL reduces diversity**
GRPO or fine-tuning improves pass@1 but reduces pass@32 and MCTS
expansion quality. Model converges to one proof style.
Mitigation: track both pass@1 and pass@32. If pass@32 drops > 20%
relative while pass@1 improves, apply checkpoint averaging before
the next EI round.

---

## 10. Repository Boundary and Release Contract

### Naming and Abstraction Principles

LeanFoundry's source code must not expose implementation names. Concrete
dependencies (Kimina, SGLang, Slime) are implementation details that may
change. The public API exposes only LeanFoundry's own abstractions:

```
Correct names in LeanFoundry source:   Incorrect (implementation leak):
  EnvBackend                             KiminaClient / kimina_url / server.Settings
  RLEngine / RLEngineBase                SlimeAdapter (internal only)
  SearchEngine                           ConcreteMCTSEngine / raw_mcts_search
  PolicyClient                           sglang_url
  /exec/step_batch                       /mcts/step_batch
```

- `lean_client` appears only in the EnvBackend adapter/launcher boundary, for
  example `leanfoundry/env_backend/kimina_backend.py`. Search, rollout, eval,
  and training code import `EnvBackend`, not `KiminaClient`.
- LeanFoundry never imports the server package. No `server.settings`,
  `server.main`, `PantographManager`, or worker classes appear in LeanFoundry.
  The current server is an app process launched by `python -m server` or by
  `lean_client.launch_server`.
- `SGLang` does not appear in LeanFoundry core. It is internal to the training
  repo or a future optional adapter and is exposed to search only through
  `PolicyClient`.
- `MCTS` does not appear as a class name or endpoint name. The search
  algorithm type (MCGS, beam, direct) is a parameter to `SearchEngine`,
  not a hardcoded identity.
- `Slime` appears only in the optional `training` extra, docs, and the
  placeholder `rl_engine/slime_adapter.py`. The landed Path-A core does not
  import Slime.

This allows swapping any implementation without changing the public API.

### The Split

The two-repo structure reflects a clean conceptual boundary:

```
Infrastructure repo:
  Owns Lean execution, search, evaluation, schemas, replay storage.
  Model-agnostic. Anyone can point it at any model endpoint.

Training repo:
  Owns model choice, training framework (Slime/Megatron/SGLang),
  data recipes, checkpoints, and experiment reports.
  Demonstrates one concrete recipe on top of the infra.
```

Dependency direction is strictly one-way:

```
training repo → infra repo
infra repo    → never imports training repo
```

### Infrastructure Repo Contents

```
env_backend/
  EnvBackend protocol and implementation factory
  kimina_backend.py: the only adapter that imports lean_client
  optional launcher wiring around lean_client.ExecServerConfig and launch_server
  no imports from the server package

lean-client dependency:
  Installed from kimina-lean-server/packages/lean-client by pinned git SHA
  Provides AsyncLeanExecBackend (the façade consumers use), the underlying
  AsyncKiminaClient / AsyncLeanExecEnv / AsyncLeanExecBatcher layers,
  ExecServerConfig + launch_server (dev-only), and shared /exec Pydantic models

backend app process:
  Runs from the kimina-lean-server checkout or image via python -m server
  Exposes /exec/create_states, /exec/step_batch, /exec/cleanup, /exec/cancel,
  /exec/limits, /exec/stats, and legacy verification/checking endpoints
  Owns Pantograph workers, StateStore, lifecycle registry, admission limiter,
  lockfile, worker reuse, timeouts, and resource safety caps

proofsearch/
  SearchEngine protocol, build_engine(config), and SearchConfig
  direct.py: direct whole-proof and completion-with-feedback search
  and_or.py: AND/OR tree search with PUCT or best-first SelectionStrategy
  expansion/backprop/lifecycle helpers for EnvBackend.step(), cleanup, cancel
  Path-A extraction: policy_examples and value_labels from runtime tree
  narrow optional proof rendering for direct/easy Path-B artifacts
  deferred: graph/MCGS, node-general HER, negation pruning, richer rendering

evals/
  Eval schemas and protocol stubs
  deferred: benchmark loaders, direct/self-correct/tree eval runners,
  pass@k, solved@budget curves, artifact manifests, report generation

schemas/
  SQL migrations (theorems, a_type_data, trajectories, policy_examples,
  state_value_labels, formal_statements_staging)
  Pydantic models for all data types
  Eval artifact schema

replay/
  ReplayStore protocol
  SQLiteReplayStore and deterministic row ids
  writer for theorem, trajectory, policy, value, and A-type artifacts

docker/
  Env Backend image (backend SHA + env_profile hash in tag)
  env_profile build scripts (Lean + Mathlib at pinned commit)
```

### Training Repo Contents

```
configs/
  stage1_sft.yaml
  stage2_whole_ei.yaml
  stage3_search_ei.yaml
  stage4_grpo.yaml
  eval_final.yaml

rollouts/
  slime_whole_proof_rollout.py
  slime_mcts_rollout.py
  slime_self_correction_rollout.py
  slime_lemma_decomposition_rollout.py  -- Aristotle-style: informal proof → lemma
                                        -- chain → formalize → MCTS per sorry block
                                        -- Uses TheoremSpec.initial_lean_block
                                        -- Training repo owns all LM orchestration;
                                        -- infra only sees sorry-initialized TheoremSpec

model_clients/
  sglang_policy_client.py     ← implements PolicyClient protocol

data_prep/
  load_leandojo.py
  load_leantree.py                  # optional; dataset choice owned here
  verify_external_a_type_data.py
  build_self_correction_data.py

scripts/
  train_sft.sh
  run_whole_ei.sh
  run_mcts_ei.sh
  run_grpo.sh
  run_eval.sh

reports/
  notebooks consuming infra eval artifact manifests
```

The training repo owns dataset choice and mixture weights, including whether
to ingest LeanTree. The infra repo owns proof-state semantics, EnvBackend
execution, replay validation, search, and eval. The training repo never calls
Lean directly. All Lean interaction goes through the infra repo's SDK:

```python
from leanfoundry.env_backend import EnvBackend
from proofsearch import MCGSSearch
from evals import run_eval
```

The concrete Kimina adapter is small and isolated:

```python
# leanfoundry/env_backend/kimina_backend.py
from lean_client import AsyncLeanExecBackend

class KiminaEnvBackend(EnvBackend):
    async def connect(self) -> None:
        # One façade owns the HTTP client, proof-state env, and step batcher.
        self._backend = await AsyncLeanExecBackend.connect(
            self.base_url, env_profile=self.env_profile
        )
```

All other LeanFoundry modules depend on `EnvBackend`; this adapter is the only
place that knows the current backend is Kimina-shaped.

### PolicyClient: The API Boundary

The search engine in the infra repo depends only on an abstract protocol,
not on SGLang or any specific inference framework:

```python
class PolicyClient(Protocol):
    async def sample_proofs(
        self,
        prompts: list[str],
        n: int,
        params: dict
    ) -> list[str]: ...

    async def sample_tactics(
        self,
        states: list[FactorizedProofState],
        n: int,
        params: dict
    ) -> list[list[str]]: ...

    async def estimate_values(
        self,
        states: list[ProofState]
    ) -> list[float]: ...
```

The training repo's `sglang_policy_client.py` implements this protocol
using SGLang. Anyone else can implement it with vLLM, Transformers,
an API model, or a rule-based system for ablations.

### Versioning Contract

The training repo pins the infra repo by exact git SHA:

```yaml
# infra.lock (in training repo root)
infra_repo: github.com/your-org/lean-agent-infra
infra_git_sha: 9a31c7...
env_backend_image: ghcr.io/your-org/kimina-lean-server:9a31c7-env2f65ba7
lean_client_ref: 9a31c7...
env_profile: lean4.29.1_mathlib_5e932f97
```

All trajectories in the database store the infra SHA and env_profile
that produced them. All eval manifests store infra SHA + training SHA
+ model checkpoint SHA. This prevents "it worked on my machine" from
becoming the release story.

### Development Workflow

The **Docker image is the prioritized deployment path** for both dev and
release: it seals the expensive part (Lean toolchain via `setup.sh` + the
Mathlib build + the server's own venv) and exposes only an HTTP port, so the
consumer's environment needs nothing but the `lean-client` package. The
`Dockerfile` already defaults `LEAN_SERVER_MODE=exec` and `CMD python -m server`;
`compose.yaml` runs it. The real cost of standing up a server is the Lean/Mathlib
build, never Python packaging — which is exactly why it should never live inside
the consumer process.

Three ways to run the server, ranked:

```
1. Docker image (preferred, dev + release):
     docker run -e LEAN_SERVER_MODE=exec -e LEAN_SERVER_MAX_REPLS=8 \
       -p 8000:8000 projectnumina/kimina-lean-server:<tag>     # or: docker compose up
   Consumer venv holds only lean-client; zero shared environment.
   Release: pin the image by infra SHA + env_profile.

2. Server checkout with its own venv (when Docker is unavailable):
     uv sync --dev && uv run python -m server --workers 8 --port 8000
   A separate server-side environment (server deps + built Mathlib) and a
   separate process on its own host/container. LeanFoundry connects to the URL
   and never imports server modules.

3. lean_client.launch_server (dev-only, monorepo-bound):
   subprocess-spawns `python -m server`, so it only resolves when the target
   interpreter already has the server package (true in THIS monorepo, false for
   a downstream repo that pip-installed only lean-client). Not part of the
   stable consumer contract.
```

> **Current local state (2026-06-17):** only the `Dockerfile` exists in-repo —
> there is no pre-built image, and Docker is not installed on the dev machine.
> So local work uses option 2 (`uv run python -m server` from this checkout);
> building/pulling the image is the first step before treating Docker as the
> default. The consumer always reaches the server over HTTP regardless of which
> option launched it.

In all cases the training repo depends on `lean-client` (from
`packages/lean-client`, pinned by git SHA/tag) as its only Python import from
this backend repo; no server package publish/install is required downstream.
`connect()` round-trips `GET /exec/limits` (rejecting unbounded caps), which is
also the connectivity check before any real work.

---

# Part III: [EXTENSION A] Multi-Machine Scale-Out
> **Status: Designed, implementation deferred. Trigger: single-machine
> throughput is the bottleneck, not model capability.**

## 11. What Changes at Multi-Machine Scale

Single machine: all communication is loopback or shared memory.
Multi-machine introduces three new problems:

**Problem 1: REPL scaling**
Lean execution (CPU-bound) needs to scale independently of GPU training.
On one machine the CPU:GPU ratio is fixed by hardware. At scale, add
CPU-only machines for Lean without buying GPUs.

**Problem 2: Routing**
With many Lean backend machines, requests need per-message routing with
a global queue. A naive load balancer causes connection pinning (the
Harmonic v1/v2 failure mode).

**Problem 3: Shared replay buffer**
Search processes on many machines all produce trajectories simultaneously.
Training needs a globally consistent replay buffer.

## 12. Multi-Machine Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Training Cluster                    │
│  Megatron across 3+ GPU nodes (NCCL via InfiniBand) │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  SGLang Cluster │  (2-4 GPU nodes, Slime-managed)
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │  Shared Replay  │  PostgreSQL or Redis Streams
              │  Buffer         │  all search nodes write here
              └────────┬────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
  Search Node 1   Search Node 2   Search Node N
  (search, asyncio) (search, asyncio) (search, asyncio)
       └───────────────┼───────────────┘
                       │  TCP
              ┌────────▼────────┐
              │   REPL Router   │  Custom C++ (Harmonic v3 equivalent)
              │   (global queue)│
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
    Lean Backend 1  Backend 2    Backend N
    Env Backend     Env Backend  Env Backend
    (CPU-only,      (CPU-only,   (CPU-only,
     preemptible)    preemptible) preemptible)
```

## 13. REPL Router: Reproducing Harmonic v3

The most critical component to build. Harmonic's C++ router is not
open source but its full design is described in their Sep 2025 blog post.

**Key design principles from Harmonic v3:**

1. Simple binary protocol (not gRPC, not WebSocket)
2. Backends connect TO the router (inverted direction)
3. Global request queue with per-CPU tracking
4. No connection pinning: per-message routing

**Message format:**
```
| request_id (8 bytes) | command (1 byte) | response_count (2 bytes) |
| data_len (4 bytes) | data (...) |

Commands:
  0x01  REGISTER   backend → router: "I have N CPUs"
  0x02  REQUEST    client → router: "execute this tactic"
  0x03  RESPONSE   backend → router: "here is the result"
  0x04  FORWARD    router → backend: "execute this"
  0x05  DELIVER    router → client: "here is your result"
  0x06  HEARTBEAT  any → any: keepalive on idle connection
```

**Why inverted backend connection direction:**

Normal load balancer (reverse proxy): router connects to backends,
needs health checks, service discovery, timeout management.

Harmonic's approach: backends connect TO the router and send REGISTER.
TCP disconnect = backend gone. No health checks or service discovery
needed. When a GCP preemptible instance is preempted, TCP drops,
router automatically re-queues in-flight requests.

**Router C++ pseudocode:**

```cpp
class REPLRouter {
    std::queue<Request> pending_queue;
    std::map<BackendId, BackendState> backends;
    std::map<uint64_t, ClientConn*> inflight;

    void on_backend_connect(Connection* conn) {
        auto msg = conn->read();
        assert(msg.command == REGISTER);
        backends[conn->id] = {
            .conn = conn,
            .total_cpus = msg.data.cpu_count,
            .idle_cpus = msg.data.cpu_count
        };
        drain_queue();
    }

    void on_client_request(Connection* client, Request req) {
        inflight[req.request_id] = client;
        auto backend = find_idle_backend();
        if (backend) {
            forward_to_backend(backend, req);
            backend->idle_cpus--;
        } else {
            pending_queue.push(req);
        }
    }

    void on_backend_response(BackendId id, Response resp) {
        auto client = inflight[resp.request_id];
        client->send(resp);
        inflight.erase(resp.request_id);
        backends[id].idle_cpus++;
        drain_queue();
    }

    void on_backend_disconnect(BackendId id) {
        // Re-queue in-flight requests from this backend
        for (auto& req : backends[id].inflight_requests)
            pending_queue.push(req);
        backends.erase(id);
        drain_queue();
    }

    void drain_queue() {
        while (!pending_queue.empty()) {
            auto backend = find_idle_backend();
            if (!backend) break;
            auto req = pending_queue.front();
            pending_queue.pop();
            forward_to_backend(backend, req);
            backend->idle_cpus--;
        }
    }
};
```

**Autoscaling algorithm (run every 60 seconds):**

```python
def autoscale(router_metrics, cluster):
    Lq   = router_metrics.queue_length
    Rmin = router_metrics.requests_last_minute
    Bmin = router_metrics.avg_backends_last_minute

    if Lq >= Rmin:
        # Queue will take > 1 min to clear. Scale to clear in Cm minutes.
        Cm = 5.0
        P = Rmin / max(Bmin, 1)          # requests per backend per minute
        target = (Rmin + (Lq / Cm)) / P
        cluster.set_min_replicas(int(target) + 1)
    else:
        # Queue draining fine. Let GKE CPU utilization autoscaling take over.
        cluster.set_min_replicas(1)
```

This algorithm reduced Harmonic's scale-up time from 2 hours to 10 minutes.
The key insight: GKE's default autoscaling only sees "CPUs are busy" — it
cannot see queue depth. This formula uses queue depth to determine how many
machines are actually needed.

## 14. State Portability (Stateless Backends)

The key that makes multi-machine Lean execution work. Proof states travel
with requests rather than being stored on backends.

Harmonic found state files compress to ~8% of original size with zstd.

```python
# After running a tactic, export state and compress
state_bytes = lean_repl.export_state(state_id)
compressed = zstd.compress(state_bytes)   # 50MB → ~4MB typical
state_token = base64.b64encode(compressed).decode()

# Next request carries state inline
router.send({
    "command": "mcts_step",
    "state_token": state_token,
    "tactic": "ring"
})

# Backend decompresses and imports before executing
state_bytes = zstd.decompress(base64.decode(request.state_token))
lean_repl.import_state(state_bytes)
result = lean_repl.run_tactic(request.tactic)
```

## 15. Distributed Replay Buffer

Single machine: SQLite (WAL mode).
Multi-machine: PostgreSQL or Redis Streams.

**PostgreSQL** (simpler, up to ~100 search nodes):
```python
async def save_trajectory(pool, trajectory):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO trajectories
            (id, theorem_id, env_profile, tactics, proof, model_version)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, trajectory.id, trajectory.theorem_id,
            trajectory.env_profile, json.dumps(trajectory.tactics),
            trajectory.proof, trajectory.model_version)
```

**Redis Streams** (higher throughput):
```python
# Search nodes publish
redis.xadd("trajectories", {
    "theorem_id": theorem_id,
    "tactics": json.dumps(tactics),
    "proof": proof,
    "model_version": str(model_version)
})

# Training nodes consume
entries = redis.xread({"trajectories": last_id}, count=256, block=1000)
```

## 16. Single → Multi Migration Path

The single-machine design was built to minimize migration friction:

```
Single machine               Multi-machine equivalent
────────────────────────────────────────────────────
Env Backend (localhost)  →   Env Backend pool behind REPL Router
Unix socket              →   TCP to router address
SQLite                   →   PostgreSQL or Redis Streams
SGLang (local)           →   SGLang cluster (Slime-managed)
Megatron (local GPUs)    →   Megatron across training nodes (NCCL)
```

The search process and MCTS algorithm code does not change at all.
The custom Slime rollout code does not change.
Only URLs in configuration files change.

Suggested migration order:
1. Move Lean backends to CPU-only preemptible machines + REPL router
2. Move replay buffer to PostgreSQL
3. Add training GPU nodes (Megatron scales via NCCL)
4. Add SGLang nodes (Slime router manages)

---

# Part IV: [EXTENSION B] Autoformalization Data Pipeline
> **Status: Architecture outlined, implementation PENDING RESEARCH.
> Do not build until the core system produces satisfactory results on
> LeanDojo novel_premises split. Key design decisions require empirical
> data from training runs.**

## 17. Why LeanDojo Alone Is Not Enough

LeanDojo's 98k theorems are sufficient to bootstrap, but Expert Iteration
exhausts useful signal after 10-20 iterations:

```
Iteration 1:  model proves 5k easy theorems → trains on them
Iteration 5:  those theorems are trivial, need harder ones
Iteration 15: most of LeanDojo below the model's frontier
```

Additionally, LeanDojo is entirely from Mathlib: biased toward certain
mathematical areas, no competition math, no graduated difficulty control.

Autoformalization produces a theorem pipeline that scales with model
capability, continuously providing theorems at the model's frontier.

## 18. Formalization Pipeline

```
Informal source (textbook, competition archive, research paper)
    ↓
Step 1: LLM translates statement to Lean 4 draft
    ↓
Step 2: Kimina /verify checks syntax and type correctness
    ↓ (on error)
Step 3: LLM receives errors, corrects draft (repeat up to N times)
    ↓ (on Kimina accept)
Step 4: Semantic judge LLM scores faithfulness (0-1)
    ↓ (if score > threshold)
Step 5: Deduplication check (embedding similarity)
    ↓
Insert into formal_statements_staging with all provenance fields
    ↓ (after manual spot-check or sufficient judge score)
Promote to theorems table as B-type data
```

## 19. Difficulty Estimation

Do not add all formalized statements with equal priority. Estimate
difficulty to control the training curriculum:

```python
async def estimate_difficulty(theorem, model, env_backend, quick_budget=20):
    proof = await search(theorem, model, env_backend, budget=quick_budget)
    if proof and proof.tactics_used <= 5:
        return "easy"      # use only for SFT warmup data
    elif proof:
        return "frontier"  # high value for Expert Iteration
    else:
        return "hard"      # queue for future iterations
```

## 20. Informal Source Priority and Scaling Roadmap

Extension B is deferred. It is not a hidden Stage 1 dependency and should not
appear in the core pipeline diagram. Activate it only after the LeanDojo-based
core pipeline has plateaued and contamination rules are stable.

**Short term after activation: baseline formalizer staging**

```
Pipeline: LLM draft → /verify statement check → semantic judge → dedup → staging table
Sources: MATH dataset, AoPS common problems, Putnam/USAMO archives,
         Lean documentation examples
Output: B-type statements in formal_statements_staging, not direct training data
Promotion: fixed split assignment + env_profile verification + contamination check
```

**Mid term: formalizer + checker duo**

Train two specialized models that improve each other:

```
Formalizer: informal statement → Lean 4 draft
  Reward signal: /verify accept rate + checker faithfulness score
  Training: same EI framework as the prover — search over Lean 4 drafts

Faithfulness checker: (informal, Lean 4 statement) → faithfulness score
  Training: human-annotated pairs + model-generated negatives
  Role: provides reward signal to formalizer training loop
```

The formalizer + checker duo is structurally symmetric to the prover +
verifier pair. The same LeanFoundry infrastructure can drive formalizer
training with a different PolicyClient and a different reward function.

**Long term: arXiv-scale data**

Work in the direction of arXiv-scale formalization only after the short- and
mid-term pipelines produce reliable, non-leaky B-type theorem streams. The core
technical challenge is dependency resolution: arXiv theorem statements often
reference paper-specific notation and definitions that must be expressed as
Lean imports or local definitions before type-checking.

This is a long-term research direction, not a short-term engineering task.
Trigger: model has saturated the mid-term theorem pool and formalizer quality
is high enough to yield meaningful throughput.

---

# Extension C: Test-Time Training Module
> **Status: Design sketch. Implement after core system is stable.
> Requires a LoRA adapter interface in the training repo.**

## 21. Motivation

Aristotle's Test-Time Training (TTT) fine-tunes the model on search traces
found during inference for a specific hard problem, then re-runs search with
the updated model. It is the highest-effort per-problem technique and most
useful for olympiad-level targets where no standard training signal exists.

TTT is blocked on components beyond the current Path-A baseline:
- search traces rich enough for per-problem fine-tuning
- node-general HER or another extraction path that can train from a target
  theorem's local traces
- a PolicyClient/model-adapter contract for loading an updated LoRA without
  restarting the search loop

TTT orchestration belongs in LeanFoundry (infra repo) because it is
model-agnostic — the same loop works for any PolicyClient implementation.
The LoRA fine-tuning step is delegated to the training repo via an
interface; the infra repo does not own an optimizer.

## 22. TTT Interface

```python
class TTTAdapter(Protocol):
    async def fine_tune(
        self,
        samples: list[TrainingSample],
        base_checkpoint: str,
        lora_rank: int,
        steps: int,
    ) -> str:
        """Fine-tune a LoRA adapter on samples.
        Returns path/ID of updated adapter."""
        ...

    async def reload(self, adapter_id: str) -> None:
        """Hot-swap SGLang to serve base model + adapter."""
        ...
```

The training repo implements `TTTAdapter` using SGLang's LoRA loading API.
LeanFoundry calls it; LeanFoundry does not contain optimizer code.

## 23. TTT Loop

```python
async def test_time_train(
    theorem: TheoremSpec,
    policy: PolicyClient,
    adapter: TTTAdapter,
    env_backend: EnvBackendClient,
    config: TTTConfig,
) -> ProofResult | None:

    for round in range(config.max_rounds):
        # 1. Search with current policy
        result = await mcgs_search(theorem, policy, env_backend,
                                   budget=config.search_budget)
        if result.proved:
            return result

        # 2. Extract training signal from search traces (HER)
        samples = extract_her_samples(result.search_graph)
        if not samples:
            break

        # 3. Fine-tune LoRA adapter on traces
        adapter_id = await adapter.fine_tune(
            samples,
            base_checkpoint=config.base_checkpoint,
            lora_rank=config.lora_rank,
            steps=config.fine_tune_steps,
        )

        # 4. Reload policy with updated adapter
        await adapter.reload(adapter_id)
        policy = policy.with_adapter(adapter_id)

    return None
```

## 24. TTT Scope

TTT is an evaluation-time capability, not a training-time technique.
It does not replace Stages 1-4 of the training pipeline. It is invoked
during evaluation on hard targets (olympiad problems, PutnamBench) after
the standard training pipeline is complete.

TTT results are not folded back into the main A-type training set without
careful deduplication and env_profile verification. Search traces from TTT
sessions may be used to expand B-type data for future training iterations,
but this requires the same provenance tracking as any external data.

---

# Part V: [EXTENSION D] Controlled Algorithm Ablation Study
> **Status: Design sketch. Run after Stage 1 checkpoint and a hygiene-
> passed curated pool exist. This Part is additive — it does not change
> Stages 2-4, their dynamic frontier filtering, or their adaptive exit
> criteria. Those remain the production "how far can we go" recipe.
> Extension D answers a different, narrower question under its own
> frozen conditions, run alongside the core pipeline rather than
> replacing any part of it.**

## 25. Motivation and Relationship to the Core Pipeline

Stages 2-4 are optimized for one thing: maximize solved@budget on the
held-out splits, by any combination of whole-proof EI, search-based EI, and GRPO,
with the frontier and exit criteria adapting to the live policy at every
iteration. That design question is "how far can we go." It is deliberately
not a controlled comparison — Stage 3's queue is defined as Stage 2's
leftovers, exit criteria are adaptive, and nothing about the pipeline holds
still long enough to isolate why a given combination works.

Extension D asks a different question: holding the base checkpoint, the
theorem-to-round assignment, and total compute fixed, which training
algorithm produces a better prover, and through which mechanism? This
requires arms that do NOT adapt their own curriculum or escalate
their own queues — the opposite of what makes Stages 2-4 effective in
production. Hence a separate Part, a separate frozen curriculum, and
its own smaller-scale arms, rather than instrumentation bolted onto the
core pipeline.

Three camps, not two, motivate the arm design below:

```
Camp 1 — outcome-only:
  whole-proof EI / RL. Training target is "did the whole proof verify."
  No search at any stage, including data collection.

Camp 2 — search-as-discovery-only:
  search (best-first or MCGS) finds proofs that direct sampling cannot,
  but the training target stays flat — same as Camp 1, just on a better
  set of discovered proofs. No value loss, no HER-derived auxiliary
  samples feed the gradient. This is closest to BFS-Prover and to
  DeepSeek-Prover-V1.5's RMaxTS-for-data-collection role.

Camp 3 — search-with-shaped-credit:
  MCGS/tree search + value function + HER-style auxiliary data, where
  the search structure itself produces additional training signal beyond
  "proof found" — value labels on searched states and, once implemented,
  HER subproofs from unsolved roots. This is a future full arm; the current
  production baseline has Path-A policy/value extraction but not graph/MCGS
  or node-general HER.
```

Camp 1 vs. Camp 2 isolates whether better proof *discovery* explains an
improvement. Camp 2 vs. Camp 3 isolates whether shaped credit assignment
adds anything beyond discovery quality. Conflating these (comparing Camp 1
directly to Camp 3, as most published comparisons do) cannot tell you
which mechanism is responsible for any observed gap.

## 26. Frozen Curriculum

Stage 2/3/4's dynamic pass_rate-based filtering is left exactly as
specified in §7 for the production pipeline. Extension D defines a
**separate, frozen** curriculum used only by its own arms:

```
1. From the shared Stage 1 checkpoint, compute whole-proof pass@N
   (fixed N, e.g. 32) once for every theorem in the curated pool.

2. Assign each theorem to a difficulty bucket and a training round
   from that single pass@N pass. Freeze this assignment.

3. Every arm in Extension D trains on the identical theorem-to-round
   mapping for every round. Only the algorithm applied to that fixed
   set varies between arms.
```

This is the fix for the coupling problem in the production pipeline:
there, Stage 3's queue is defined as Stage 2's pass_rate=0 leftovers, so
"what a given stage trains on" depends on what earlier stages already
did. That dependency is a feature for "how far can we go" and a confound
for a controlled comparison. Extension D removes it by construction, at
the cost of not adapting — which is exactly the cost that makes it
unsuitable as a replacement for Stages 2-4.

## 27. Algorithm Arms

```
Arm W       — whole-proof EI only (§7 Stage 2 mechanics, no Stage 3
              escalation, frozen curriculum). Camp 1.

Arm W+SC    — Arm W, plus self-correction (Format 3: failed proof +
              Lean errors → revision). Still a flat outcome-only
              target. Camp 1, with one round of real compiler feedback.

Arm S-disc  — Search (§3.2-3.3) finds proofs per the frozen
              curriculum; train ONLY on found whole-proof and
              tactic-sequence pairs. No value loss term. No HER
              extraction. Isolates discovery quality from shaped
              credit assignment. Camp 2.

Arm S-noval — Best-first search, no value model, ranking by policy
              probability only (BFS-Prover-style). Isolates whether a
              learned value function specifically matters within
              search, independent of HER. Camp 2 variant.

Arm S-full  — Full shaped-credit mechanics (§3.2-3.5): graph/MCGS or
              tree search, value function, and HER-style auxiliary data
              under the frozen curriculum instead of the dynamic pass_rate=0
              queue. Camp 3.
```

Arms are seeded from the identical Stage 1 checkpoint. None of them
feed into or modify the production Stage 2-4 pipeline's own state;
each Extension D arm keeps its own replay buffer and checkpoint
lineage.

## 28. Compute Ledger and Budget Enforcement

Three meters, tracked per arm per round:

```
generation: prefill + decode tokens (SGLang), convertible to FLOPs
training:   tokens through the optimizer (Megatron)
verifier:   per-request Lean CPU-seconds and wall time, from /exec
            diagnostics — measured on the worker, excluding queue wait
```

Every request and policy call carries a `budget_account_id`; a metering
service decrements the per-cell budget and refuses requests once
exhausted. This is enforcement, not just measurement — without hard
caps, the search arms can silently overspend relative to Arm W and the
comparison stops being interpretable.

For cross-architecture pass@K reporting, adopt DeepSeek-Prover-V1.5's
budget-alignment convention as the primary axis: K = total proofs
generated for single-pass arms (W, W+SC), K = N×S×T for best-first
search (attempts × tactics per expansion × expansion iterations,
S-noval), K = N×T for tree search (attempts × model generations
invoked, S-disc and S-full). Report the three-ledger breakdown
secondarily — invocation counts alone hide the cost of macro-tactics
(`aesop`, `nlinarith`, `simp_all`), which can each absorb a single
"node" worth of K while consuming a highly variable amount of actual
Lean CPU time. Log macro-tactic call rate per arm as a covariate for
this reason.

## 29. Crossed Evaluation Design

Evaluating each arm only in its native inference mode confounds
"did this training algorithm produce a better core policy" with "does
this inference protocol help regardless of how the policy was trained."
Because a whole-proof attempt is just a sequence of tactics, any
whole-proof-trained arm can be wrapped in post-hoc external search at
inference by truncating at tactic boundaries and resuming search from
the resulting state — this is exactly DeepSeek-Prover-V1.5's
truncate-and-resume mechanism for RMaxTS, applied here as an evaluation
tool rather than a training-time method. Symmetrically, a search-trained
arm can be run single-shot by sampling from its policy head and ignoring
the value head and tree apparatus entirely.

```
                    eval: native            eval: cross-wrapped
Arm W           |   single-shot pass@K   |  + post-hoc search wrapper
Arm W+SC        |   self-correct pass@K  |  + post-hoc search wrapper
Arm S-disc      |   MCGS solved@budget   |  single-shot from policy head
Arm S-noval     |   BFS solved@budget    |  single-shot from policy head
Arm S-full      |   MCGS solved@budget   |  single-shot from policy head
```

Diagonal cells are the deployment-relevant numbers: this training
recipe, deployed in its own native mode, at matched budget. Off-diagonal
cells isolate mechanism. DeepSeek-Prover-V1.5's own published RMaxTS
result (whole-proof-RL policy + search wrapper: 60.2% → 63.5% on
miniF2F) is a useful external sanity-check reference for the Arm
W / cross-wrapped cell before trusting this study's own numbers.

All results are stratified by required-proof-length / difficulty bucket
(from the frozen §26 assignment). The predicted result is a
difficulty-dependent crossover, not a uniform ranking: outcome-only
arms (W, W+SC) are expected to match or beat the search arms on short
proofs, where direct sampling already succeeds often enough to get
nonzero reward, and to lag increasingly on long, compositional proofs,
where outcome-only reward is exactly zero until the model can already
nearly solve the whole thing — while Arm S-full's value labels and HER
subproofs give nonzero training signal on theorems it never fully
solves. Arm S-disc sitting between Arm W and Arm S-full on long proofs
would indicate the gap is mostly about discovery quality; Arm S-disc
tracking Arm W instead would indicate the gap is mostly about shaped
credit assignment.

## 30. Hygiene Defaults for the Curated Pool

Any autoformalized statement entering this study's pool must already
have passed Extension B's standard promotion gate plus the negation
check (`try_negation`, §3.5.1 / concern G5) before being added: attempt
the negation, and retire or relabel any statement that proves false or
that double-proves (both the statement and its negation succeed,
indicating a vacuous/inconsistent hypothesis set) before promotion to
this study's frozen pool. This is a pool-construction requirement
applied once, upstream of Extension D, not a variable under test here.
Extension D's arms are compared on training algorithm; statement-level
contamination tolerance is a separate, already-settled question and
should not be allowed to vary uncontrolled across arms by accident.

## 31. Outcome Variables

```
held-out solved@budget per ledger unit, stratified by difficulty bucket
compute-to-asymptote (shift) vs. final asymptote, per arm
macro-tactic call rate per arm (covariate for K-alignment, not an outcome)
value AUC / calibration error (S-disc, S-noval, S-full only)
HER rescue rate: fraction of unsolved-root search sessions yielding
  at least one verified subproof (S-disc and S-full, for comparison)
```

## 32. Scope

Run the full 5-arm × difficulty-stratified matrix at a smaller model
size than the production §5.2 base model, given compute constraints;
confirm the headline crossover (Arm W vs. Arm S-full, on the longest
difficulty bucket) at full scale only for the cell(s) that matter most
once the smaller-scale results are in. Two to three seeds on headline
cells; single-seed acceptable for the remaining diagnostic arms (S-disc,
S-noval) given their role is mechanism isolation, not the topline claim.

This Part does not modify Stage 1's checkpoint, Stage 2-4's mechanics,
or the production pipeline's own replay buffer and exit criteria in
any way. It is a separate study that reads the same Stage 1 checkpoint
and the same hygiene-passed pool, and writes to its own buffers.

---

## References

**Systems and Infrastructure**

[1] Harmonic. "Running Lean at Scale." Engineering Blog, Sep 2025.
    https://harmonic.fun/news/lean-at-scale/
    → Source for REPL service v0-v3 design, inverted backend connection
      pattern, global queueing, autoscaling, and state compression.

[2] Kimina Lean Server. project-numina/kimina-lean-server, 2025.
    https://github.com/project-numina/kimina-lean-server
    Technical report: arXiv:2504.21230
    → Source for REPL worker pool, header/body split, LRU header reuse,
      batch verification, and infotree extraction.

[3] Lean REPL. leanprover-community/repl.
    https://github.com/leanprover-community/repl
    → Underlying REPL used by Kimina. Relevant for whole-file verification
      and possible future direct REPL proof-state work.

[3a] Pantograph / PyPantograph. stanford-centaur/PyPantograph.
     https://github.com/stanford-centaur/PyPantograph
     → Source for tactic-level goal_start, load_sorry, goal_tactic,
       goal_save, and goal_load used by the v0 Env Backend worker.

[4] Slime. THUDM, 2025.
    https://github.com/THUDM/slime
    → RL post-training framework connecting Megatron training, SGLang rollout,
      custom data generation, data buffer, and weight synchronization.

[5] Qwen3.6. QwenLM/Qwen3.6, 2026.
    https://github.com/QwenLM/Qwen3.6
    Model: Qwen/Qwen3.6-27B on Hugging Face.
    → Main actor model candidate. Dense 27B, Apache 2.0, released Apr 2026,
      SGLang/vLLM/Transformers-compatible. LeanFoundry uses shorter text-only
      rollout contexts by default.

**Datasets and Lean Tooling**

[6] Yang et al. "LeanDojo: Theorem Proving with Retrieval-Augmented
    Language Models." NeurIPS 2023. arXiv:2306.15626.
    → Primary data/tooling foundation: theorem tracing, proof states, tactics,
      premises, benchmark splits, and ReProver baseline.

[7] LeanDojo-v2. "A Comprehensive Library for AI-Assisted Theorem Proving
    in Lean." NeurIPS Mathematical Reasoning and AI, 2025.
    https://leandojo.org/leandojo.html
    → Updated Lean 4 library for repository tracing, lifelong dataset
      management, agents, fine-tuning, GRPO, retrieval, and eval/deployment.

[8] LeanTree. "Accelerating White-Box Proof Search with Factorized States
    in Lean 4." arXiv:2507.14722, 2025.
    Tool: https://github.com/Kripner/leantree
    Dataset: https://huggingface.co/datasets/ufal/leantree
    → Prior for factorized intermediate proof states, metavariable-coupling
      checks, branch parallelism, proof-tree data, and white-box Lean
      proof-state tooling.

[9] Lean Copilot. "Towards Large Language Models as Copilots for Theorem
    Proving in Lean." arXiv:2404.12534, 2024/2025.
    → Lean-native LLM inference framework for tactic suggestion, proof search,
      and premise selection.

[10] Loogle. nomeata/loogle.
     https://github.com/nomeata/loogle
     → Mathlib search tool. Not used as a core training-time tool. If later
       retrieval experiments are conducted, the index must be built from the
       same Mathlib commit as the env_profile.

**Algorithms, Provers, and Models**

[11] Harmonic. "Aristotle: IMO-level Automated Theorem Proving."
     arXiv:2510.01346, 2025.
     → Source for MCGS, AND/OR hardest-child priority, Expert Iteration,
       HER, value labels, state-equivalence caveats, TTT, and autoformalization.

[12] DeepMind. "Olympiad-level formal mathematical reasoning with
     reinforcement learning." Nature, 2025.
     → AlphaProof/AlphaGeometry formal reasoning system; 2024 IMO silver-level
       result and AlphaZero-style RL over Lean proof search.

[13] ByteDance Seed. "BFS-Prover: Scalable Best-First Tree Search for
     LLM-based Automatic Theorem Proving." arXiv:2502.03438, 2025.
     → Best-first tree search, self-filtering Expert Iteration, DPO from
       compiler feedback, and MiniF2F results.

[14] ByteDance Seed. "BFS-Prover-V2: Scaling up Multi-Turn Off-Policy RL
     and Multi-Agent Tree Search for LLM Step-Provers." 2025.
     https://github.com/ByteDance-Seed/BFS-Prover-V2
     → Open step-level prover system with multi-stage EI, adaptive tactic
       filtering, periodic retraining, and planner-enhanced inference search.

[15] Moonshot AI. "Kimina-Prover Preview: Towards Large Formal Reasoning
     Models with Reinforcement Learning." arXiv:2504.11354, 2025.
     → Whole-proof formal reasoning pattern, Kimina Lean Server release, and
       RL results without MCTS/value/process reward in the public recipe.

[16] project-numina/kimina-prover-rl.
     https://github.com/project-numina/kimina-prover-rl
     → Open RL pipeline around Kimina-style verifier rewards and long-context
       formal reasoning; useful baseline but not MCGS runtime infra.

[17] Lin et al. "Goedel-Prover-V2: Scaling Formal Theorem Proving with
     Scaffolded Data Synthesis and Self-Correction." arXiv:2508.03613, 2025.
     → Three SFT formats, pass-rate bucketing, self-correction, GRPO recipe,
       checkpoint averaging, and Goedel-Formalizer-V2 design.

[18] Xin et al. "DeepSeek-Prover-V1.5: Harnessing Proof Assistant Feedback
     for Reinforcement Learning and Monte-Carlo Tree Search." arXiv:2408.08152,
     2024.
     → RLPAF, intermediate-success filtering for GRPO, and RMaxTS-style search.

[19] Xin et al. "DeepSeek-Prover-V2." arXiv:2504.21801, 2025.
     → Subgoal decomposition, recursive proof synthesis, structure consistency
       reward, and two-phase EI/RL pipeline.

[20] Kripner. nanoproof, 2026.
     https://github.com/Kripner/nanoproof
     → Minimal open AlphaProof/HyperTree Proof Search-style implementation
       using LeanTree server, MCTS prover, evaluation, and distributed RL loop.

[21] InternLM2.5-StepProver. "Advancing Automated Theorem Proving via
     Critic-Guided Search." arXiv:2410.15700, 2024/2025.
     → Step prover with critic-guided search and expert iteration.

[22] MPS-Prover. "Advancing Stepwise Theorem Proving by Multi-Perspective
     Search and Data Curation." arXiv:2505.10962, 2025.
     → Multi-perspective tree search, learned critics, heuristic diversity,
       and post-training data curation.

[23] StepFun-Prover Preview. "Let's Think and Verify Step by Step."
     arXiv:2507.20199, 2025.
     → Tool-integrated reasoning model and RL framework; reports 70% pass@1
       on miniF2F-test with the 32B preview model.

[24] Leanabell-Prover-V2. "Verifier-integrated Reasoning for Formal Theorem
     Proving via Reinforcement Learning." arXiv:2507.08649, 2025.
     → Verifier-integrated CoT/RL with multi-turn Lean feedback.

[25] Seed-Prover 1.5. "Mastering Undergraduate-Level Theorem Proving via
     Learning from Experience." arXiv:2512.17260, 2025.
     → Large-scale agentic RL and test-time scaling; reports strong PutnamBench
       and Putnam 2025 results.

[26] Prover Agent. "An Agent-based Framework for Formal Mathematical Proofs."
     arXiv:2506.19923, 2025.
     → Agentic framework coordinating informal reasoning, a formal prover,
       Lean feedback, and auxiliary lemma generation.

[27] Polu & Han. "Generative Language Modeling for Automated Theorem
     Proving." arXiv:2009.03393, 2020.
     → Original Expert Iteration formulation for neural theorem proving.

[28] Shao et al. "DeepSeekMath." arXiv:2402.03300, 2024.
     → Source for GRPO used in Stage 4.

---

# Appendix: Aristotle Algorithm Reference

This appendix documents the Aristotle algorithm as understood from the paper
and subsequent analysis. It serves as the authoritative algorithmic reference
for LeanFoundry's MCGS implementation. Where LeanFoundry deviates or extends,
deviations are noted explicitly.

---

## A.1 States and Actions

**State**: a tuple of (goal expressions, local context expressions, local
variable names). Two states are equivalent iff all three match exactly.
Variable names are part of the key — `hP : P ⊢ Q` and `h1 : P ⊢ Q` are
different states. This is pragmatic: renaming would require expensive
normalization.

**Action**: a text string of one or more Lean tactics, optionally prefixed
with inline natural-language comments. Actions are deduplicated by the state
transitions they produce, not by text equality.

**State splitting rule**: after an action produces multiple goals, split into
independent states only if no goal contains metavariables. If metavariables
are present, bundle all goals as one state — the metavariable value chosen for
one goal affects the other. Goals from explicit `sorry` placeholders are always
split and never permitted to have metavariables.

When states are deduplicated across proof paths, the hypertree becomes a
hypergraph. LeanFoundry gates graph merging behind a correctness acceptance
test (see concern A1). In v0.1–v0.2, tree search only.

---

## A.2 AND/OR Structure

- **State (OR node)**: proved if ANY action succeeds.
- **Action (AND node)**: succeeds only if ALL child states are proved.

The MCTS iteration cycle is strictly sequential within one theorem:
select → expand → backpropagate → repeat.

**UCB** governs action selection at the current state:
```
UCB(a) = value_estimate(a) + c * prior(a) * sqrt(parent_visits) / (1 + action_visits)
```
Prior is empirical frequency of the action in policy samples, NOT sequence
log-probability (log-prob biases against actions with multiple equivalent
textual representations).

**LCB** governs AND-child selection: among the AND-children of the selected
action, descend into the one with the lowest lower confidence bound — the
hardest, most uncertain subgoal. Rationale: the bottleneck determines whether
the action can ever succeed. Budget flows primarily to the hardest child. The
easier child receives budget only when the harder one is proved or when a
fresh iteration selects a completely different action from the root.

LCB and UCB are independent mechanisms operating at different levels. LCB
selects which AND-child to descend into at the parent action level. UCB
selects which action to try at the state level.

---

## A.3 Negation Pruning

For each single-goal state `⊢ P`, a synthetic action is added to the pool:
prove `¬P` in the same local context. This action competes under normal UCB
selection and receives a full sub-search across potentially many iterations.
It is NOT a one-step check.

If `¬P` is proved: state is marked DISPROVED. "Dead" propagates upward through
all parent AND-nodes. Any AND-node with a DISPROVED child is eliminated from
its parent OR-node.

If `¬P` is not proved: the action accumulates visit count, UCB score declines,
search moves on naturally.

LeanFoundry: implemented as `try_negation=False` flag in expansion (see G5).

---

## A.4 Parallelism

**Within one theorem**: MCTS iterations are strictly sequential. The only
parallelism is outside the selected state's worker lease. N candidate tactics
are generated together for the selected state, but Env Backend receives them as
one proof-state expansion item. One worker loads that state once and evaluates
the tactic candidates internally. The backend manager must not flatten those
tactics into separate jobs.

**Across theorems**: independent MCGS instances. No shared state, no
coordination. Trivially parallel.

**Cross-theorem batching**: when many theorems are searched concurrently,
policy and Env Backend calls arrive in bursty patterns. The full Slime custom
rollout owns the search orchestration; its EnvClient microbatches proof-state
expansion items into `/exec/step_batch` calls, like Kimina batches many
independent code-check items in one `/check` request. Design parameters are the
microbatch window, max items per request, and backpressure policy (see R1).

---

## A.5 Trajectory Representation

A proof with AND-splits is a tree, not a sequence:

```python
@dataclass
class TacticNode:
    state: FactorizedProofState
    tactic: str
    children: list["TacticNode"]  # AND-children after split; single for linear step

@dataclass
class ProofTree:
    roots: list[TacticNode]   # one solved initial backend state per root
    rendered_lean: str         # canonical text reconstructed from tactic history
```

Runtime search initialization has a synthetic wrapper above these roots:

```
synthetic root OR-state
  synthetic initialization AND-action
    real initial backend state 1
    real initial backend state 2
    ...
```

That wrapper is not training data. It exists only because `SearchTree` has one
root while `/exec/create_states` may return multiple initial states. Extraction
starts below the wrapper and turns each real initial state into one
`ProofTree.roots` entry by pairing the state with its proved action.

Three uses from one representation:
- `rendered_lean`: optional Path-B proof text for final verification
- Depth-first traversal: Path-A policy examples with `proof_prefix`
- Any proved subtree: future HER candidate (must pass `/exec/verify`)

The tree structure is required to reconstruct Lean's branching syntax
(`case inl =>`, `case inr =>`). LeanFoundry: stored as serialized TacticNode
tree in `trajectories.tactic_sequence` (see G3).

---

## A.6 Value Training

Three label types:

| State | Label | Weight | `disproved` |
|-------|-------|--------|-------------|
| On accepted-step proved Path-A path | 1 | 1.0 | False |
| Negation proved (DISPROVED) | 0 | 1.0 | True |
| Searched but not proved, ≥50 tactics tried | 0 | 0.25* | False |

*Weight 0.25 is a guess. Needs ablation (see R3).

In v0, runtime `OPEN` is not a durable resume state. A root that is still
`OPEN` when the configured attempt budget stops becomes the top-level
`EXHAUSTED`/unproved attempt outcome. That outcome is not theorem falsity, but
it may produce censored value-label data after the effort gate.

States searched with < min_effort tactics are excluded — too few attempts
to confidently label as negative.

Root-outcome interpretation:

- Runtime structural `PROVED` states can emit Path-A policy/value training data
  after accepted `/exec` steps and the sorry/admit guard. Top-level
  `SearchStatus.PROVED` and whole-proof artifacts still require the extracted
  `rendered_lean` to pass final `/exec/verify`.
- `DISPROVED` means a negation search proved falsity for the state being
  disproved. The original state receives a full-weight value-negative label.
  The tactics inside the negation proof can be positive policy data for the
  synthetic negation goal, not for the original goal.
- `EXHAUSTED`/unproved means the attempt stopped with the root still `OPEN`
  after spending its configured effort. This is a censored negative only; it may
  train value after the effort gate, but it is not policy data and not
  mathematical falsity.

---

## A.7 Policy Training

Each `(state, action)` pair in any found proof subgraph is a supervised example.
The action string includes hidden CoT tokens, inline comments, and formal
tactic text. Inline comments must be preserved — they are persistent memory
across the proof and the model must learn to produce them (see G4).

Hindsight Experience Replay multiplies examples by treating proved subtrees
as standalone root theorems. Amplification of 10–50× is claimed by Aristotle;
actual `her_verified_multiplier` depends on how many candidates survive
Kimina re-verification (see R2).

---

## A.8 Outer Lemma Pipeline (Training Repo Concern)

The lemma decomposition loop is an algorithm-specific training recipe, not
an infrastructure component. It belongs in the training repo as a rollout
class. LeanFoundry's only required support is `TheoremSpec.initial_lean_block`
(see G1), which receives the sorry-initialized Lean block the training repo
constructs.

Pipeline (training repo):
1. LM generates informal proof of target theorem
2. LM decomposes into lemma chain (individually simple)
3. LM formalizes lemma statements to Lean 4 type signatures
4. Submit with `:= by sorry` to `EnvBackendClient.verify`; relay errors; correct
5. Build `initial_lean_block` with all sorry-d lemmas + main theorem
6. Pass to `SearchEngine` via `TheoremSpec(initial_lean_block=block)`
7. SearchEngine runs MCGS; lemma dependencies handled by Lean automatically
8. Read `ProofTree.roots` to determine proved/unproved initial states
9. If fails: annotate and revise decomposition; go to step 1

The informal proof context conditioning the policy during search is provided
by the training repo's prompt builder; the infra PolicyClient interface does
not need a dedicated field for it.

Both Aristotle-style (informal proof revision) and DeepSeek-Prover-V2-style
(structured subgoal decomposition) fit this interface — they differ only in
how the training repo builds the `initial_lean_block`.
