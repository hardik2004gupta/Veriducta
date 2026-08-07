# Good First Issues

Pre-analyzed tasks for first-time contributors. Each entry includes: what to change, where to find it, and what test to add.

---

## Documentation (no code required)

### GFI-001 - Add curl examples to API docs

**What**: Add `curl` command examples for all API endpoints to `docs/api_reference.md` (or create it).

**Where**: `api/routers/` - read each route handler; document the request format and response schema.

**Test**: Not required for documentation-only changes.

**Good for**: First contributors who want to understand the API surface.

---

### GFI-002 - Add docstrings to private helper functions

**What**: Several private functions in `utils/` and `ingestion/` are missing docstrings. Add one-line docstrings explaining the input/output contract.

**Where**: Run `grep -rn "def _" utils/ ingestion/ retrieval/` and identify functions without docstrings.

**Rule**: Private functions don't require Args/Returns/Raises format - a single sentence is sufficient.

**Test**: Not required.

---

## Tests (add coverage without changing functionality)

### GFI-003 - Test temporal filter with future effective date

**What**: Add a test that verifies chunks with `effective_date` in the future (relative to `query_date`) are rejected with reason `"not_yet_effective"`.

**Where**: `tests/test_retrieval.py` (add to the temporal filter section).

**How**:
```python
def test_temporal_filter_future_document_rejected_with_correct_reason():
    # Create a mock chunk with effective_date = "2099-01-01"
    # Set query_date = "2024-01-01"
    # Assert rejection_reason == "not_yet_effective"
```

**Existing reference**: `tests/test_retrieval.py` has examples of filter tests to follow.

---

### GFI-004 - Test ConfigurationSnapshot immutability

**What**: Add a test that verifies a `ConfigurationSnapshot` cannot be mutated after creation (Pydantic frozen model).

**Where**: `tests/test_schemas.py`

**How**:
```python
def test_configuration_snapshot_is_immutable():
    snapshot = ConfigurationSnapshot(...)
    with pytest.raises(ValidationError):  # or PydanticUserError
        snapshot.hash = "different_hash"
```

---

### GFI-005 - Test RRF fusion with absent candidates

**What**: Add a test verifying that a candidate present in only one ranked list (BM25 but not dense, or dense but not BM25) receives the correct implicit rank (101) in the absent list and the correct RRF score.

**Where**: `tests/test_retrieval.py`

**Formula**: `rrf_score = 1/(60+rank_bm25) + 1/(60+101)` for a candidate with BM25 rank but absent from dense list.

---

## Frontend (TypeScript/Next.js, no backend required)

### GFI-006 - Add loading skeleton to Evidence Log page

**What**: The Evidence Log page (`frontend/app/(app)/evidence/page.tsx`) shows a blank state while data loads. Add a skeleton loader component.

**Where**: `frontend/app/(app)/evidence/page.tsx`

**How**: Use TailwindCSS `animate-pulse` for skeleton UI. Match the style of the existing loading states in the Dashboard page.

**Test**: `npx tsc --noEmit` must pass; `npm run build` must succeed.

---

### GFI-007 - Add keyboard shortcut for Ask page

**What**: Add a global keyboard shortcut (e.g., `/` to focus the search input on the Ask page) similar to how many developer tools work.

**Where**: `frontend/app/(app)/ask/page.tsx`

**How**: Use `useEffect` + `addEventListener("keydown", ...)` with `useRef` for the input element.

**Test**: Manually verify focus behavior; TypeScript check must pass.

---

## Small Code Improvements

### GFI-008 - Add `--dry-run` flag to validate_sidecars.py

**What**: `scripts/validate_sidecars.py` validates sidecars and reports errors but always returns exit code 0. Add a `--dry-run` flag that prints what would be done without making changes (currently no changes are made anyway, but the flag signals intent) and a `--strict` flag that exits 1 on any validation error.

**Where**: `scripts/validate_sidecars.py`

**How**: Use `argparse` (already in stdlib). `--strict` exits with code 1 if any sidecar fails validation.

**Test**: `tests/test_scripts.py` - test that `--strict` exits 1 with an intentionally malformed sidecar.

---

### GFI-009 - Add `chunk_count` to ingestion log output

**What**: After a successful ingestion run, log the total number of chunks created (child + parent separately) alongside the document count.

**Where**: `ingestion/ingestor.py` - find the final log line after ingestion completes.

**How**: Add `child_chunk_count` and `parent_chunk_count` as structured key-value pairs in the existing structlog call.

**Test**: `tests/test_ingestion.py` - verify the log event is emitted with the correct chunk counts on a small test corpus.

---

### GFI-010 - Add type annotation to evidence log reader

**What**: `observability/evidence_log.py` has one function where the return type annotation uses `dict` without type parameters. Add full type parameters.

**Where**: Run `mypy --strict observability/evidence_log.py` to identify the exact location.

**Test**: `make type-check` must pass after the change.

---

## Multi-LLM Support (larger, good for contributors with LLM API experience)

### GFI-011 - Add OpenAI generator adapter

**What**: Implement `generation/openai_generator.py` as a concrete implementation of `BaseGenerator` using the OpenAI Python SDK.

**Contract**: The class must implement:
- `generate(query, context) -> StructuredAnswer`
- `replay_with_context(query, context_override, config_override) -> StructuredAnswer`

**Config**: Add `OpenAISettings` to `config/settings.py` with `model`, `api_key`, `max_tokens` fields.

**Test**: `tests/test_generation.py` - mock the OpenAI API call; verify the `StructuredAnswer` schema matches the Anthropic generator's output.

**Note**: This is a larger contribution (~200 lines). Comment on the issue before starting so no one else works on it simultaneously.
