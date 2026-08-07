# Veriducta - Architecture Explained

*Plain-language walkthrough of every architectural decision.*

---

## Why Eight Layers?

Most projects of this size don't need eight layers. Veriducta needs them because causal attribution requires substituting individual pipeline stages with counterfactual configurations - without affecting adjacent stages.

If retrieval and generation are coupled (e.g., the generator knows how retrieval works), you can't test "what would have happened if a different retrieval had run?" without changing the generator. The strict dependency constraint makes each layer independently substitutable.

The eight layers:
1. **Foundation** (schemas, utils, config, core): pure types and infrastructure, zero business logic
2. **Ingestion**: PDF → chunks → Qdrant + BM25 index
3. **Retrieval**: query → ranked candidates with full scores
4. **Generation**: context → structured answer with citations
5. **Verification**: claims → NLI entailment + counterevidence status
6. **Causal Replay**: historical trace → root-cause attribution
7. **Evaluation**: 40 gold questions + 60 corruption cases → metric scorecard
8. **API**: HTTP surface, no business logic

---

## The Evidence Log Design

The evidence log is the core design innovation. Without it, the replay engine would need to re-run inference to answer counterfactual questions, which is both slow and non-deterministic.

**Append-only JSONL**: One JSON line per query, written once, never modified. Corrections go to a separate log. This is a deliberate constraint - immutability makes traces reliable for forensic use.

**SQLite byte-offset index**: The index stores the exact file position of each entry. `SELECT byte_offset FROM traces WHERE trace_id = ?` → `file.seek(byte_offset)` → `file.readline()`. No full-file scan.

**Why not a database?** A database (PostgreSQL) would store JSON blobs that require deserializing the full trace to find a specific field. The JSONL + index pattern gives the same O(1) lookup with smaller operational footprint. The evidence log is read-heavy and append-only - a perfect fit for this pattern.

---

## Hybrid Retrieval: Why Both BM25 and Dense?

BM25 and dense retrieval have complementary failure modes.

**Dense retrieval** is good at semantic matching but poor at exact terminology. A query for `"OSHA 1926.1153"` in a dense index retrieves semantically similar OSHA standards, not necessarily the specific subpart.

**BM25** is excellent at exact terminology matches but fails on paraphrase queries. "Maximum permissible exposure" and "PEL" may not co-occur in the same document, but dense retrieval bridges the gap.

**RRF fusion** combines both ranked lists without requiring training data. The formula `1/(60 + rank)` gives higher weight to candidates that ranked well in both lists, and a meaningful fallback score (1/161) to candidates present in only one list.

The `k=60` constant is from Cormack et al. (2009). Changing it without re-benchmarking is inadvisable - it was tuned for the distribution of rank gaps in combined ranked lists.

---

## Boundary-Aware Chunking: The Core Problem

Hierarchical chunking (parent chunks at 1400–1600 tokens, child chunks at 200–400 tokens) is standard practice. The "boundary-aware" constraint is specific to Veriducta.

**The problem it solves**: A 512-token window can split a regulatory clause mid-sentence. When that happens, the first half of the clause ranks in BM25/dense retrieval, but the second half (containing the operative quantity) starts a new chunk that may not rank well on its own.

**How boundary detection works**: The chunker maintains a list of regex patterns that indicate section boundaries (e.g., `"^\d+\.\d+"`, `"Employer(s)? (must|shall)"`, `"Section \d+"`, `"Table \d+"`). When a window would cross one of these patterns, it terminates at the boundary and starts a new child chunk.

**Why this matters for attribution**: The chunking failure corpus documents are specifically the documents where boundary-naive and boundary-aware chunking produce different splits at critical clauses. Stage 1 ablation can only detect a chunking failure if those documents are in the corpus and the alternative collection exists.

---

## The NLI Verification Pipeline

After generation, every claim in the structured answer is verified against its cited chunk using a cross-encoder NLI model (cross-encoder/nli-deberta-v3-base).

**3-class heuristic** (why 3 and not 2):

Regulatory and technical documents contain conditional language that NLI models score ambiguously - not because they're uncertain, but because the language is genuinely conditional. `"Unless the employer can demonstrate..."` is not a contradiction; it's a condition. The `ambiguous-conditional` class captures these without flagging them as contradictions.

**Counterevidence retrieval** (5-step algorithm): For claims with ≥ 2 key entities, the system constructs a contrastive BM25 query (`{entities} exception OR limitation OR superseded OR warning OR caution`) and retrieves the top 10 candidates. These candidates are then scored against the claims using the same NLI model. This catches cases where the corpus contains evidence that contradicts the answer, even if that evidence wasn't in the original retrieval context.

---

## ConfigurationSnapshot Hashing

Every pipeline stage that makes configuration-dependent decisions creates a `ConfigurationSnapshot` - an immutable, SHA-256 hashed record of its parameters.

**Why hashing**: The replay engine needs to determine whether a historical trace used the same chunking configuration as the current production configuration. Without a hash, this comparison is impossible (the configurations may have different in-memory representations but identical semantics, or vice versa).

**Immutability**: A snapshot is created once and never modified. If a configuration parameter changes, a new snapshot is created with a new hash. Historical traces retain their original snapshot hash, enabling comparison across ingestion runs.

This is the mechanism that makes Stage 1 ablation meaningful: the trace's `chunking_snapshot_hash` identifies exactly which chunking configuration produced the chunks being analyzed.

---

## The Temporal Validity System

Regulatory corpora have supersession relationships: a newer standard replaces an older one on a specific effective date. Without temporal filtering, a query made in 2024 may retrieve chunks from a 1989 standard that was superseded in 2016.

**Version graph**: A `networkx` DiGraph where nodes are documents and directed edges represent supersession (`A supersedes B` means B is outdated once A's effective date is reached).

**Filter logic at query time**:
1. Get the query date from the request
2. For each retrieved candidate, get its document's effective date and expiry date
3. Check version graph: does a superseding document exist with effective date ≤ query date?
4. If yes: reject with reason `"superseded"`
5. If effective date > query date: reject with reason `"not_yet_effective"`

**Mandatory by design**: There is no parameter to disable temporal filtering in the production code path. Supersession errors are silent (the answer is wrong but looks plausible) and dangerous in regulatory contexts.

---

## Why Claude Sonnet 4.6 for Generation?

1. **JSON schema enforcement**: The structured generation pipeline needs reliable JSON output. Claude Sonnet 4.6 with explicit schema instructions achieves ≥ 9/10 first-try compliance. Schema validation failures trigger up to 2 retries with correction instructions.

2. **Citation grounding**: The system prompt requires each claim to cite its supporting chunk by ID. Claude Sonnet 4.6 follows citation instructions with high reliability.

3. **Max tokens 2048**: Sufficient for a 3–5 claim structured answer with citations and confidence tags. Longer responses introduce verbosity without quality improvement.

The model choice was validated on 10 representative pilot queries before Phase 11 was implemented. Schema compliance rate on pilot: 9.5/10.
