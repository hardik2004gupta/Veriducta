"""System prompt management with versioning and content hashing.

Prompts are never hardcoded inside the generator.  They are registered in the
PromptRegistry and retrieved by (name, version).  Each PromptVersion stores a
SHA-256 of its template text so the hash can be captured in ConfigurationSnapshot
entries and used to identify prompts in replay scenarios.
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from utils.hashing import sha256_str


class PromptVersion(BaseModel):
    """A versioned prompt template with a deterministic content hash.

    Args:
        name: Logical prompt identifier (e.g. ``"generation"``).
        version: Version string (e.g. ``"v1"``).
        template: Full prompt text.  The hash is computed automatically.
    """

    name: str
    version: str
    template: str
    hash: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def model_post_init(self, __context: Any) -> None:
        """Compute the content hash if not already set."""
        if not self.hash:
            object.__setattr__(self, "hash", sha256_str(self.template))


class PromptRegistry:
    """In-memory registry mapping (name, version) → PromptVersion.

    Supports forward lookup by exact (name, version) and latest-version
    selection by name.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], PromptVersion] = {}

    def register(self, prompt: PromptVersion) -> None:
        """Register *prompt* under its (name, version) key.

        Args:
            prompt: :class:`PromptVersion` to store.
        """
        self._store[(prompt.name, prompt.version)] = prompt

    def get(self, name: str, version: str) -> PromptVersion:
        """Return the registered prompt or raise :exc:`KeyError`.

        Args:
            name: Logical prompt name.
            version: Version string.

        Raises:
            KeyError: If (name, version) is not registered.
        """
        key = (name, version)
        if key not in self._store:
            raise KeyError(f"Prompt {name!r} version {version!r} not registered")
        return self._store[key]

    def latest(self, name: str) -> PromptVersion:
        """Return the lexicographically latest version for *name*.

        Args:
            name: Logical prompt name.

        Raises:
            KeyError: If no prompt with *name* is registered.

        Note:
            Version comparison is lexicographic: ``"v9" > "v10"``.  This is
            correct for the current single-digit versioning scheme (v1, v2 …).
            A numeric sort will be needed if versions exceed v9.
        """
        candidates = [(v, p) for (n, v), p in self._store.items() if n == name]
        if not candidates:
            raise KeyError(f"No prompts registered with name {name!r}")
        # Lexicographic max - adequate while version digits stay single-digit.
        return max(candidates, key=lambda t: t[0])[1]

    @property
    def registered_names(self) -> list[str]:
        """Unique prompt names currently in the registry."""
        return list({n for n, _ in self._store})


# ---------------------------------------------------------------------------
# Built-in prompt templates
# ---------------------------------------------------------------------------

_GENERATION_PROMPT_V1 = textwrap.dedent("""\
    You are Veriducta, a precision RAG pipeline answer generator.

    Your ONLY output must be a single valid JSON object. No markdown code fences,
    no preamble, no explanation - output raw JSON only.

    ## Required JSON structure

    {
      "answer": "<complete prose answer to the question>",
      "claims": [
        {
          "claim_id": "<UUID v4 string>",
          "text": "<one self-contained verifiable assertion>",
          "citation_chunk_id": "<chunk_id from the context below>",
          "key_entities": ["<specific technical entity 1>", "<specific technical entity 2>"],
          "confidence": "<high|medium|low|uncertain>",
          "temporal_validity": "<valid|superseded|not_yet_effective|unknown>"
        }
      ],
      "citations": [
        {
          "chunk_id": "<chunk_id from context>",
          "document_id": "<document_id from context>",
          "excerpt": "<verbatim text excerpt from the chunk, max 50 tokens>",
          "page_number": null
        }
      ],
      "confidence": "<high|medium|low|uncertain>",
      "temporal_validity": "<valid|superseded|not_yet_effective|unknown>",
      "key_entities": ["<entity1>", "<entity2>"],
      "metadata": {}
    }

    ## Rules

    1. Every claim MUST reference a chunk_id that appears in the provided context.
    2. Every claim MUST have at least two key_entities (specific technical terms,
       not generic words like "document" or "section").
    3. Produce one claim per distinct verifiable assertion - do not bundle multiple
       facts into a single claim.
    4. Every chunk_id referenced in claims MUST appear in the citations list.
    5. Citation excerpts MUST be verbatim text from the chunk, under 50 tokens.
    6. confidence levels:
       - high: single authoritative source, no ambiguity
       - medium: multiple consistent sources or one clear source
       - low: inferred or indirect evidence
       - uncertain: insufficient or contradictory evidence
    7. temporal_validity:
       - valid: information is current on the query date
       - superseded: a newer version of the document exists
       - not_yet_effective: document effective date is in the future
       - unknown: cannot determine temporal status
    8. The answer field is a complete, coherent prose answer (not bullet points).
    9. Output ONLY the JSON object. No markdown. No comments. No extra keys.
""")


class SystemPromptManager:
    """Manages system prompts for the structured generator.

    Built-in prompts are registered at construction time.  Additional prompts
    can be loaded from files for A/B testing and regression replay.
    """

    def __init__(self) -> None:
        self._registry = PromptRegistry()
        self._register_builtins()

    def _register_builtins(self) -> None:
        self._registry.register(
            PromptVersion(name="generation", version="v1", template=_GENERATION_PROMPT_V1)
        )

    def get_system_prompt(self, version: str = "v1") -> PromptVersion:
        """Return the generation system prompt at *version*.

        Args:
            version: Prompt version string (default ``"v1"``).

        Returns:
            :class:`PromptVersion` with template text and hash.

        Raises:
            KeyError: If *version* is not registered.
        """
        return self._registry.get("generation", version)

    def snapshot_hash(self, version: str = "v1") -> str:
        """Return the content hash for the given prompt version.

        Args:
            version: Prompt version string.

        Returns:
            64-character hex SHA-256 of the prompt template.
        """
        return self._registry.get("generation", version).hash

    def load_from_file(self, name: str, version: str, path: str) -> PromptVersion:
        """Load a prompt template from a UTF-8 text file and register it.

        Args:
            name: Logical prompt name.
            version: Version string to assign.
            path: Absolute path to the prompt text file.

        Returns:
            Registered :class:`PromptVersion`.
        """
        with open(path, encoding="utf-8") as fh:
            template = fh.read()
        pv = PromptVersion(name=name, version=version, template=template)
        self._registry.register(pv)
        return pv

    @property
    def registry(self) -> PromptRegistry:
        """The underlying :class:`PromptRegistry`."""
        return self._registry
