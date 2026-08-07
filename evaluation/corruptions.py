"""Synthetic corruption dataset - seed data and builder for the benchmark.

:data:`CORRUPTIONS_SEED` contains 60 engineered failure cases covering four
pipeline stages (retrieval, chunking, reranker, generation).
:class:`CorruptionDatasetBuilder` loads from the seed or from a JSONL file
and provides conversion helpers for the replay engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from evaluation.schemas import EvaluationCorruptionCase
from replay.models import CorruptionCase

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Seed data - 60 corruption cases
# 20 retrieval  (5 swap, 5 supersession_removal, 5 bm25_zeroing, 5 top_k_reduction)
# 15 chunking   (all boundary_naive; first 10 are realistic boundary errors)
# 15 reranker   (5 top1_forcing, 5 cross_encoder_bypass, 5 score_inversion)
# 10 generation (4 unstructured_prompt, 3 contradictory_injection, 3 token_truncation)
# ---------------------------------------------------------------------------

CORRUPTIONS_SEED: list[dict[str, Any]] = [
    # ============================================================ RETRIEVAL SWAP (001-005)
    {
        "case_id": "corr-retrieval-001",
        "question_id": "qa-001",
        "corruption_type": "retrieval_swap",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Replace the correct H2S ceiling-concentration chunk with a chunk about noise exposure limits from a different OSHA document.",
        "corrupted_configuration": {"retrieval": {"swap_supporting_with": "osha-hazcom-ch-0012"}},
        "expected_quality_delta": -0.45,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "original_chunk": "osha-resp-prot-ch-0012",
            "replacement_chunk": "osha-hazcom-ch-0012",
            "swap_rank": 1,
        },
        "notes": "Swapped chunk is topically adjacent (OSHA safety) but factually wrong domain.",
    },
    {
        "case_id": "corr-retrieval-002",
        "question_id": "qa-013",
        "corruption_type": "retrieval_swap",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Swap sandstone porosity chunk with a shale gas permeability chunk that contains similar numeric ranges.",
        "corrupted_configuration": {
            "retrieval": {"swap_supporting_with": "usgs-oil-formations-ch-0067"}
        },
        "expected_quality_delta": -0.50,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "original_chunk": "usgs-oil-formations-ch-0034",
            "replacement_chunk": "usgs-oil-formations-ch-0067",
            "swap_rank": 1,
        },
        "notes": "Replacement chunk discusses millidarcy thresholds, not porosity - numerically confusing.",
    },
    {
        "case_id": "corr-retrieval-003",
        "question_id": "qa-023",
        "corruption_type": "retrieval_swap",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Replace the API 5CT J55 yield strength chunk with a P110 grade chunk that references higher thresholds.",
        "corrupted_configuration": {"retrieval": {"swap_supporting_with": "api-5ct-2022-ch-0045"}},
        "expected_quality_delta": -0.55,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "original_chunk": "api-5ct-2022-ch-0023",
            "replacement_chunk": "api-5ct-2022-ch-0045",
            "swap_rank": 1,
        },
        "notes": "P110 has 110,000 psi yield - answer with swapped chunk will state wrong grade properties.",
    },
    {
        "case_id": "corr-retrieval-004",
        "question_id": "qa-033",
        "corruption_type": "retrieval_swap",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Replace the CERCLA lead soil cleanup chunk with a RCRA industrial soil threshold chunk.",
        "corrupted_configuration": {"retrieval": {"swap_supporting_with": "epa-remed-ch-0056"}},
        "expected_quality_delta": -0.40,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "original_chunk": "epa-remed-ch-0034",
            "replacement_chunk": "epa-remed-ch-0056",
            "swap_rank": 1,
        },
        "notes": "Industrial threshold is 750 mg/kg - answer with swapped chunk will cite wrong value.",
    },
    {
        "case_id": "corr-retrieval-005",
        "question_id": "qa-038",
        "corruption_type": "retrieval_swap",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Replace the RCRA hazardous waste determination chunk with a CERCLA liability chunk.",
        "corrupted_configuration": {"retrieval": {"swap_supporting_with": "epa-remed-ch-0023"}},
        "expected_quality_delta": -0.38,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "original_chunk": "epa-remed-ch-0045",
            "replacement_chunk": "epa-remed-ch-0023",
            "swap_rank": 1,
        },
        "notes": "CERCLA liability chunk changes the procedural framing of the answer.",
    },
    # ======================================= RETRIEVAL SUPERSESSION_REMOVAL (006-010)
    {
        "case_id": "corr-retrieval-006",
        "question_id": "qa-003",
        "corruption_type": "retrieval_supersession_removal",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Disable temporal filter so the superseded 1910.146 construction-scoping language is included alongside the current 1926.1203 standard.",
        "corrupted_configuration": {"retrieval": {"temporal_filter_enabled": False}},
        "expected_quality_delta": -0.45,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "removed_filter": "supersession",
            "injected_doc_ids": ["osha-conf-space-1910"],
        },
        "notes": "Without the temporal filter the 1910 general-industry scoping language appears; model answers 'yes it applies'.",
    },
    {
        "case_id": "corr-retrieval-007",
        "question_id": "qa-017",
        "corruption_type": "retrieval_supersession_removal",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Inject pre-2019 Kansas GMD rules by disabling document supersession filtering.",
        "corrupted_configuration": {"retrieval": {"temporal_filter_enabled": False}},
        "expected_quality_delta": -0.40,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "removed_filter": "supersession",
            "injected_doc_ids": ["usgs-groundwater-ks"],
        },
        "notes": "Pre-2019 allocation rules directly contradict post-2019 outcome for vested rights.",
    },
    {
        "case_id": "corr-retrieval-008",
        "question_id": "qa-024",
        "corruption_type": "retrieval_supersession_removal",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Include NIST SP 800-53 Rev 4 password complexity rules by removing version-supersession filtering.",
        "corrupted_configuration": {"retrieval": {"temporal_filter_enabled": False}},
        "expected_quality_delta": -0.35,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "removed_filter": "supersession",
            "injected_doc_ids": ["nist-sp800-r4"],
        },
        "notes": "Rev 4 mandates 8-character minimum with complexity; Rev 5 removed those requirements.",
    },
    {
        "case_id": "corr-retrieval-009",
        "question_id": "qa-034",
        "corruption_type": "retrieval_supersession_removal",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Include pre-2011 DOE dose guidance by disabling temporal filter.",
        "corrupted_configuration": {"retrieval": {"temporal_filter_enabled": False}},
        "expected_quality_delta": -0.28,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "removed_filter": "supersession",
            "injected_doc_ids": ["doe-rad-prot"],
        },
        "notes": "Pre-2011 guidance omits ALARA framework; answer will lack ALARA context.",
    },
    {
        "case_id": "corr-retrieval-010",
        "question_id": "qa-007",
        "corruption_type": "retrieval_supersession_removal",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Inject older fall protection guidance that predates the 2019 update to 1910.28.",
        "corrupted_configuration": {"retrieval": {"temporal_filter_enabled": False}},
        "expected_quality_delta": -0.30,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "removed_filter": "supersession",
            "injected_doc_ids": ["osha-fall-prot"],
        },
        "notes": "Pre-update fall protection thresholds differ for some activity categories.",
    },
    # ============================================== RETRIEVAL BM25_ZEROING (011-015)
    {
        "case_id": "corr-retrieval-011",
        "question_id": "qa-005",
        "corruption_type": "retrieval_bm25_zeroing",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Zero BM25 scores so dense-only retrieval handles the IDLH respirator query; IDLH is a rare abbreviation that dense retrieval may not rank correctly.",
        "corrupted_configuration": {"retrieval": {"bm25_weight": 0.0, "dense_weight": 1.0}},
        "expected_quality_delta": -0.25,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "bm25_weight": 0.0,
            "dense_weight": 1.0,
        },
        "notes": "IDLH and SCBA are exact-match abbreviations; dense retrieval under-ranks them.",
    },
    {
        "case_id": "corr-retrieval-012",
        "question_id": "qa-014",
        "corruption_type": "retrieval_bm25_zeroing",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Zero BM25 scores for the tight gas permeability query; 'millidarcy' is a technical abbreviation requiring lexical match.",
        "corrupted_configuration": {"retrieval": {"bm25_weight": 0.0, "dense_weight": 1.0}},
        "expected_quality_delta": -0.22,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "bm25_weight": 0.0,
            "dense_weight": 1.0,
        },
        "notes": "Dense retrieval may retrieve adjacent permeability discussion without the 0.1 millidarcy threshold.",
    },
    {
        "case_id": "corr-retrieval-013",
        "question_id": "qa-019",
        "corruption_type": "retrieval_bm25_zeroing",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Zero BM25 so the ShakeAlert magnitude threshold query relies on dense-only retrieval.",
        "corrupted_configuration": {"retrieval": {"bm25_weight": 0.0, "dense_weight": 1.0}},
        "expected_quality_delta": -0.20,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "bm25_weight": 0.0,
            "dense_weight": 1.0,
        },
        "notes": "'ShakeAlert' is a proper noun requiring BM25 for reliable match.",
    },
    {
        "case_id": "corr-retrieval-014",
        "question_id": "qa-026",
        "corruption_type": "retrieval_bm25_zeroing",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "low",
        "description": "Zero BM25 for annular BOP test pressure query; specific numeric range requires lexical match.",
        "corrupted_configuration": {"retrieval": {"bm25_weight": 0.0, "dense_weight": 1.0}},
        "expected_quality_delta": -0.18,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "bm25_weight": 0.0,
            "dense_weight": 1.0,
        },
        "notes": "Annular BOP sub-section is lexically distinct; dense-only retrieval retrieves general BOP chapter.",
    },
    {
        "case_id": "corr-retrieval-015",
        "question_id": "qa-035",
        "corruption_type": "retrieval_bm25_zeroing",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Zero BM25 for the NEPA categorical exclusion query; 'categorical exclusion' and 'NMFS' require exact term matching.",
        "corrupted_configuration": {"retrieval": {"bm25_weight": 0.0, "dense_weight": 1.0}},
        "expected_quality_delta": -0.22,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "bm25_weight": 0.0,
            "dense_weight": 1.0,
        },
        "notes": "NMFS clause will be missed by dense retrieval alone.",
    },
    # =========================================== RETRIEVAL TOP_K_REDUCTION (016-020)
    {
        "case_id": "corr-retrieval-016",
        "question_id": "qa-002",
        "corruption_type": "retrieval_top_k_reduction",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Reduce final top-k from 8 to 3 for the confined space permit criteria query; second supporting chunk drops out.",
        "corrupted_configuration": {"retrieval": {"top_k": 3}},
        "expected_quality_delta": -0.25,
        "pipeline_trace_id": "",
        "corruption_parameters": {"top_k": 3, "original_top_k": 8},
        "notes": "Second supporting chunk (1910-ch-0024) provides the permit issuance criteria example.",
    },
    {
        "case_id": "corr-retrieval-017",
        "question_id": "qa-011",
        "corruption_type": "retrieval_top_k_reduction",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "low",
        "description": "Reduce top-k to 2 for the HazCom SDS accessibility query.",
        "corrupted_configuration": {"retrieval": {"top_k": 2}},
        "expected_quality_delta": -0.20,
        "pipeline_trace_id": "",
        "corruption_parameters": {"top_k": 2, "original_top_k": 8},
        "notes": "The electronic access clarification chunk drops out at top-k=2.",
    },
    {
        "case_id": "corr-retrieval-018",
        "question_id": "qa-020",
        "corruption_type": "retrieval_top_k_reduction",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "low",
        "description": "Reduce top-k to 2 for the normal fault hanging wall query.",
        "corrupted_configuration": {"retrieval": {"top_k": 2}},
        "expected_quality_delta": -0.18,
        "pipeline_trace_id": "",
        "corruption_parameters": {"top_k": 2, "original_top_k": 8},
        "notes": "Graben structure context chunk drops out but answer remains partially correct.",
    },
    {
        "case_id": "corr-retrieval-019",
        "question_id": "qa-028",
        "corruption_type": "retrieval_top_k_reduction",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Reduce top-k to 3 for the API RP 2D crane load chart query.",
        "corrupted_configuration": {"retrieval": {"top_k": 3}},
        "expected_quality_delta": -0.22,
        "pipeline_trace_id": "",
        "corruption_parameters": {"top_k": 3, "original_top_k": 8},
        "notes": "The weather-resistant/permanent-affixing clause chunk drops out at top-k=3.",
    },
    {
        "case_id": "corr-retrieval-020",
        "question_id": "qa-036",
        "corruption_type": "retrieval_top_k_reduction",
        "ground_truth_root_cause": "retrieval",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Reduce top-k to 3 for the surface owner split-estate notice query; state-specific bonding chunk drops out.",
        "corrupted_configuration": {"retrieval": {"top_k": 3}},
        "expected_quality_delta": -0.30,
        "pipeline_trace_id": "",
        "corruption_parameters": {"top_k": 3, "original_top_k": 8},
        "notes": "State bonding requirements chunk is rank 5-6; falls outside reduced window.",
    },
    # ====================================== CHUNKING BOUNDARY_NAIVE (001-015)
    # 001-010: realistic boundary errors (mid-sentence or ambiguous section break)
    {
        "case_id": "corr-chunking-001",
        "question_id": "qa-006",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": True,
        "severity": "high",
        "description": "Naive chunking splits hot work permit steps 4-5 at the section header 'Fire Watch Requirements'; step 5 (supervisor sign-off) appears only in the next chunk.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.35,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "mid_procedure_step",
            "affected_content": "supervisor sign-off requirement (step 5)",
        },
        "notes": "Realistic because 'Fire Watch Requirements' is a styled heading mid-paragraph in the source PDF.",
    },
    {
        "case_id": "corr-chunking-002",
        "question_id": "qa-008",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": True,
        "severity": "high",
        "description": "Naive chunking splits the rescue service requirements at 'Rescue Equipment' subheading; written program documentation requirement (item 5) moves to next chunk.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.32,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "mid_list_item",
            "affected_content": "written rescue procedure documentation (item 5)",
        },
        "notes": "Rescue equipment subheading has inconsistent bold formatting triggering premature split.",
    },
    {
        "case_id": "corr-chunking-003",
        "question_id": "qa-021",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": True,
        "severity": "high",
        "description": "Naive chunking splits hydraulic fracturing sequence steps 6-7 (isolation plug + toe-to-heel repeat) at an unnumbered diagnostic monitoring note.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.38,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "mid_numbered_list",
            "affected_content": "steps 6-7 of multi-stage sequence",
        },
        "notes": "Diagnostic monitoring note has no list marker; naive splitter treats it as section boundary.",
    },
    {
        "case_id": "corr-chunking-004",
        "question_id": "qa-025",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": True,
        "severity": "medium",
        "description": "Naive chunking splits BOP test condition list at 'Following Control System Failure' subheading; condition (4) appears only in the successor chunk.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.28,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "mid_conditional_list",
            "affected_content": "condition 4 - control system failure trigger",
        },
        "notes": "The subheading appears as an inline bold phrase that naive tokenizer misclassifies as section break.",
    },
    {
        "case_id": "corr-chunking-005",
        "question_id": "qa-037",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": True,
        "severity": "high",
        "description": "Naive chunking splits the offshore permit agency list at 'Environmental Agency Coordination' header; NMFS MMPA authorization (item 3) and subsequent agencies move to next chunk.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.40,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "mid_ordered_list",
            "affected_content": "agencies 3-5 of the permit coordination list",
        },
        "notes": "Missing NMFS causes model to answer with only BSEE/BOEM, omitting three required agencies.",
    },
    {
        "case_id": "corr-chunking-006",
        "question_id": "qa-032",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": True,
        "severity": "medium",
        "description": "Naive chunking splits deepwater cementing requirements at 'Temperature Considerations' header; temperature regression clause moves to next chunk.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.25,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "mid_requirements_list",
            "affected_content": "temperature regression constraint",
        },
        "notes": "Temperature regression is a critical deepwater-specific constraint omitted when chunk boundary is naive.",
    },
    {
        "case_id": "corr-chunking-007",
        "question_id": "qa-015",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": True,
        "severity": "medium",
        "description": "Naive chunking splits artesian vs. unconfined aquifer comparison at 'Unconfined Aquifer Properties' subheading; the unconfined water-table characterisation moves to successor chunk.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.30,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "mid_comparison_paragraph",
            "affected_content": "unconfined aquifer pressure-head description",
        },
        "notes": "Without the unconfined half of the comparison the model can only describe artesian conditions.",
    },
    {
        "case_id": "corr-chunking-008",
        "question_id": "qa-006",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": True,
        "severity": "medium",
        "description": "Second hot work permit variant: naive chunking splits at 'Atmospheric Monitoring Protocol' subheading, isolating the 10% LEL threshold from the fire watch requirement.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.22,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "mid_procedure_criterion",
            "affected_content": "10% LEL threshold verification (step 3)",
        },
        "notes": "Slightly less severe than corr-chunking-001 because LEL value is still in the retrieved chunk.",
    },
    {
        "case_id": "corr-chunking-009",
        "question_id": "qa-008",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": True,
        "severity": "medium",
        "description": "Second rescue service variant: naive chunking splits at 'Annual Evaluation Requirement' note, isolating simulation-based testing language.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.24,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "mid_annual_requirement",
            "affected_content": "simulated emergency annual evaluation (item 1)",
        },
        "notes": "Annual evaluation with simulated emergencies is an assessable requirement; omission is material.",
    },
    {
        "case_id": "corr-chunking-010",
        "question_id": "qa-021",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": True,
        "severity": "medium",
        "description": "Second fracturing variant: naive boundary splits at 'Proppant Schedule' table caption, losing the overflush flush step (step 5) from the procedure description.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.20,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "before_table_caption",
            "affected_content": "overflush fluid step (step 5)",
        },
        "notes": "Table caption triggers naive splitter; step 5 is in the table header row of the next chunk.",
    },
    # 011-015: non-realistic (clean paragraph/section break)
    {
        "case_id": "corr-chunking-011",
        "question_id": "qa-015",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": False,
        "severity": "low",
        "description": "Non-realistic boundary split: naive chunking separates aquifer definition from pressure-head discussion at a clear section break between 'Aquifer Types' and 'Hydraulic Properties'.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.15,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "clean_section_boundary",
            "affected_content": "hydraulic pressure head discussion",
        },
        "notes": "Clean break; less severe because section boundary is visually obvious.",
    },
    {
        "case_id": "corr-chunking-012",
        "question_id": "qa-032",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": False,
        "severity": "low",
        "description": "Non-realistic boundary: deepwater cementing temperature clause is at a numbered section start - clean split that any chunker would make.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.12,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "clean_numbered_section",
            "affected_content": "temperature regression clause",
        },
        "notes": "Boundary aware and naive produce same split here; delta reflects omission only.",
    },
    {
        "case_id": "corr-chunking-013",
        "question_id": "qa-037",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Non-realistic variant: offshore permit agency list split at 'Environmental Permits' bold heading after a blank line - clear section boundary.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.20,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "clean_bold_heading",
            "affected_content": "EPA and USCG requirements (items 4-5)",
        },
        "notes": "Items 4-5 still move to next chunk; severity is medium because 3 agencies are still omitted.",
    },
    {
        "case_id": "corr-chunking-014",
        "question_id": "qa-006",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": False,
        "severity": "low",
        "description": "Non-realistic variant: hot work permit step list split between steps 2 and 3 at a clear blank-line paragraph break in the source PDF.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.10,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "blank_line_paragraph",
            "affected_content": "step 3 onward (LEL threshold and fire watch)",
        },
        "notes": "Retriever still fetches both chunks; quality delta reflects join failure not full omission.",
    },
    {
        "case_id": "corr-chunking-015",
        "question_id": "qa-025",
        "corruption_type": "chunking_boundary_naive",
        "ground_truth_root_cause": "chunking",
        "is_realistic_boundary_error": False,
        "severity": "low",
        "description": "Non-realistic variant: BOP test interval conditions split at 'Testing Procedures' section title - unambiguous section boundary.",
        "corrupted_configuration": {"chunking": {"boundary_aware": False}},
        "expected_quality_delta": -0.10,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "boundary_aware": False,
            "split_location": "titled_section_start",
            "affected_content": "condition 3 (21-day interval) and condition 4",
        },
        "notes": "Clean section title; boundary-aware and naive produce same split. Benchmark lower bound.",
    },
    # ============================================== RERANKER TOP1_FORCING (001-005)
    {
        "case_id": "corr-reranker-001",
        "question_id": "qa-001",
        "corruption_type": "reranker_top1_forcing",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Force the BM25-top-1 candidate (a respirator maintenance chapter, not the H2S exposure limit) to rank first, displacing the correct exposure limit chunk.",
        "corrupted_configuration": {"reranker": {"force_top1_chunk_id": "osha-resp-prot-ch-0002"}},
        "expected_quality_delta": -0.48,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "forced_rank1_chunk_id": "osha-resp-prot-ch-0002",
            "original_rank1_chunk_id": "osha-resp-prot-ch-0012",
        },
        "notes": "Respirator maintenance chapter appears in BM25 top-10; cross-encoder correctly ranks it out.",
    },
    {
        "case_id": "corr-reranker-002",
        "question_id": "qa-013",
        "corruption_type": "reranker_top1_forcing",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Force a shale gas description chunk to rank first for the sandstone porosity query.",
        "corrupted_configuration": {
            "reranker": {"force_top1_chunk_id": "usgs-oil-formations-ch-0089"}
        },
        "expected_quality_delta": -0.52,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "forced_rank1_chunk_id": "usgs-oil-formations-ch-0089",
            "original_rank1_chunk_id": "usgs-oil-formations-ch-0034",
        },
        "notes": "Forced chunk discusses pore pressure not porosity; answer will conflate the two.",
    },
    {
        "case_id": "corr-reranker-003",
        "question_id": "qa-023",
        "corruption_type": "reranker_top1_forcing",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Force a casing connection thread specification chunk to rank first for the J55 yield strength query.",
        "corrupted_configuration": {"reranker": {"force_top1_chunk_id": "api-5ct-2022-ch-0067"}},
        "expected_quality_delta": -0.50,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "forced_rank1_chunk_id": "api-5ct-2022-ch-0067",
            "original_rank1_chunk_id": "api-5ct-2022-ch-0023",
        },
        "notes": "Thread spec chunk contains no yield strength data; answer will be incomplete or fabricated.",
    },
    {
        "case_id": "corr-reranker-004",
        "question_id": "qa-033",
        "corruption_type": "reranker_top1_forcing",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Force a CERCLA remediation timelines chunk to rank first for the lead soil cleanup level query.",
        "corrupted_configuration": {"reranker": {"force_top1_chunk_id": "epa-remed-ch-0067"}},
        "expected_quality_delta": -0.38,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "forced_rank1_chunk_id": "epa-remed-ch-0067",
            "original_rank1_chunk_id": "epa-remed-ch-0034",
        },
        "notes": "Remediation timeline chunk lacks numeric soil thresholds; answer will be vague.",
    },
    {
        "case_id": "corr-reranker-005",
        "question_id": "qa-038",
        "corruption_type": "reranker_top1_forcing",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Force a RCRA manifesting requirements chunk (not the hazardous-waste determination procedure) to rank first.",
        "corrupted_configuration": {"reranker": {"force_top1_chunk_id": "epa-remed-ch-0078"}},
        "expected_quality_delta": -0.35,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "forced_rank1_chunk_id": "epa-remed-ch-0078",
            "original_rank1_chunk_id": "epa-remed-ch-0045",
        },
        "notes": "Manifesting chunk describes post-determination logistics, not the determination procedure itself.",
    },
    # ========================================= RERANKER CROSS_ENCODER_BYPASS (006-010)
    {
        "case_id": "corr-reranker-006",
        "question_id": "qa-004",
        "corruption_type": "reranker_cross_encoder_bypass",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Skip the cross-encoder entirely for the PSM HF threshold query; present RRF-fused candidates directly without reranking.",
        "corrupted_configuration": {"reranker": {"enabled": False}},
        "expected_quality_delta": -0.28,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "reranker_enabled": False,
            "fallback": "rrf_order",
        },
        "notes": "RRF places a general HF toxicology chunk above the PSM threshold chunk in this query.",
    },
    {
        "case_id": "corr-reranker-007",
        "question_id": "qa-009",
        "corruption_type": "reranker_cross_encoder_bypass",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Skip cross-encoder for the PSM/RMP ammonia comparison; RRF produces a different top-3 that omits the off-site consequence analysis chunk.",
        "corrupted_configuration": {"reranker": {"enabled": False}},
        "expected_quality_delta": -0.32,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "reranker_enabled": False,
            "fallback": "rrf_order",
        },
        "notes": "RRF ranks the off-site consequence chunk at position 9; it falls outside top-8 without reranking.",
    },
    {
        "case_id": "corr-reranker-008",
        "question_id": "qa-018",
        "corruption_type": "reranker_cross_encoder_bypass",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Skip cross-encoder for the structural vs. stratigraphic trap comparison; RRF order places anticline definition over seal integrity discussion.",
        "corrupted_configuration": {"reranker": {"enabled": False}},
        "expected_quality_delta": -0.26,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "reranker_enabled": False,
            "fallback": "rrf_order",
        },
        "notes": "Seal integrity discussion (critical for the comparative answer) moves outside top-8.",
    },
    {
        "case_id": "corr-reranker-009",
        "question_id": "qa-027",
        "corruption_type": "reranker_cross_encoder_bypass",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Skip cross-encoder for the mud weight adjustment procedure; RRF misranks the ECD/fracture gradient constraint chunk.",
        "corrupted_configuration": {"reranker": {"enabled": False}},
        "expected_quality_delta": -0.35,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "reranker_enabled": False,
            "fallback": "rrf_order",
        },
        "notes": "Without reranking, the ECD constraint chunk does not make top-8; answer omits critical constraint.",
    },
    {
        "case_id": "corr-reranker-010",
        "question_id": "qa-040",
        "corruption_type": "reranker_cross_encoder_bypass",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Skip cross-encoder for the interstate groundwater contamination jurisdiction query; RRF places federal preemption discussion above the concurrent authority clarification.",
        "corrupted_configuration": {"reranker": {"enabled": False}},
        "expected_quality_delta": -0.28,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "reranker_enabled": False,
            "fallback": "rrf_order",
        },
        "notes": "Concurrent authority chunk is rank 10 in RRF; cross-encoder promotes it to rank 3.",
    },
    # =========================================== RERANKER SCORE_INVERSION (011-015)
    {
        "case_id": "corr-reranker-011",
        "question_id": "qa-007",
        "corruption_type": "reranker_score_inversion",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "critical",
        "description": "Invert all cross-encoder scores for the fall protection height query; worst-ranked candidate becomes top-1.",
        "corrupted_configuration": {"reranker": {"invert_scores": True}},
        "expected_quality_delta": -0.60,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "invert_scores": True,
        },
        "notes": "Score inversion produces random worst-case retrieval context; answer has no relationship to query.",
    },
    {
        "case_id": "corr-reranker-012",
        "question_id": "qa-012",
        "corruption_type": "reranker_score_inversion",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "critical",
        "description": "Invert cross-encoder scores for the concurrent fall protection standards query.",
        "corrupted_configuration": {"reranker": {"invert_scores": True}},
        "expected_quality_delta": -0.58,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "invert_scores": True,
        },
        "notes": "Score inversion; the least relevant generic OSHA chapter ranks first.",
    },
    {
        "case_id": "corr-reranker-013",
        "question_id": "qa-022",
        "corruption_type": "reranker_score_inversion",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "critical",
        "description": "Invert cross-encoder scores for the hydraulic fracturing groundwater contamination query.",
        "corrupted_configuration": {"reranker": {"invert_scores": True}},
        "expected_quality_delta": -0.55,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "invert_scores": True,
        },
        "notes": "Score inversion; well integrity discussion moves to rank 38-40.",
    },
    {
        "case_id": "corr-reranker-014",
        "question_id": "qa-029",
        "corruption_type": "reranker_score_inversion",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "critical",
        "description": "Invert cross-encoder scores for the BOP test interval extension query.",
        "corrupted_configuration": {"reranker": {"invert_scores": True}},
        "expected_quality_delta": -0.57,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "invert_scores": True,
        },
        "notes": "Score inversion; variance provisions chunk moves to bottom; mandatory section chunk also displaced.",
    },
    {
        "case_id": "corr-reranker-015",
        "question_id": "qa-036",
        "corruption_type": "reranker_score_inversion",
        "ground_truth_root_cause": "reranking",
        "is_realistic_boundary_error": False,
        "severity": "critical",
        "description": "Invert cross-encoder scores for the surface owner split-estate notice query.",
        "corrupted_configuration": {"reranker": {"invert_scores": True}},
        "expected_quality_delta": -0.56,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "invert_scores": True,
        },
        "notes": "Score inversion; federal minimum notice chunk moves to rank 36-40; answer fabricates content.",
    },
    # ======================================= GENERATION UNSTRUCTURED_PROMPT (001-004)
    {
        "case_id": "corr-generation-001",
        "question_id": "qa-010",
        "corruption_type": "generation_unstructured_prompt",
        "ground_truth_root_cause": "generation",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Remove JSON schema enforcement and retry logic; prompt the model to answer in freeform prose. APF numeric value is expected to be lost or hallucinated.",
        "corrupted_configuration": {
            "generation": {"json_schema_enforcement": False, "output_format": "prose"}
        },
        "expected_quality_delta": -0.35,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "schema_enforcement": False,
            "output_format": "prose",
            "retries": 0,
        },
        "notes": "Without schema enforcement, per-claim citations are not produced; APF values may be rounded.",
    },
    {
        "case_id": "corr-generation-002",
        "question_id": "qa-022",
        "corruption_type": "generation_unstructured_prompt",
        "ground_truth_root_cause": "generation",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Remove schema enforcement for the hydraulic fracturing/groundwater contradiction query; model collapses contradiction to one view in freeform output.",
        "corrupted_configuration": {
            "generation": {"json_schema_enforcement": False, "output_format": "prose"}
        },
        "expected_quality_delta": -0.40,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "schema_enforcement": False,
            "output_format": "prose",
            "retries": 0,
        },
        "notes": "Prose output omits the contradicted/ambiguous_conditional verification status; model hedges are lost.",
    },
    {
        "case_id": "corr-generation-003",
        "question_id": "qa-031",
        "corruption_type": "generation_unstructured_prompt",
        "ground_truth_root_cause": "generation",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Remove schema enforcement for the out-of-corpus mud specific heat capacity query; model fabricates a value rather than acknowledging absence.",
        "corrupted_configuration": {
            "generation": {"json_schema_enforcement": False, "output_format": "prose"}
        },
        "expected_quality_delta": -0.30,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "schema_enforcement": False,
            "output_format": "prose",
            "retries": 0,
        },
        "notes": "Without structured schema, model cannot express 'not_in_corpus' state; hallucination follows.",
    },
    {
        "case_id": "corr-generation-004",
        "question_id": "qa-039",
        "corruption_type": "generation_unstructured_prompt",
        "ground_truth_root_cause": "generation",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Remove schema enforcement for the ISO 16530/API RP 90 comparison query (both absent from corpus); model produces a fabricated comparison.",
        "corrupted_configuration": {
            "generation": {"json_schema_enforcement": False, "output_format": "prose"}
        },
        "expected_quality_delta": -0.45,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "schema_enforcement": False,
            "output_format": "prose",
            "retries": 0,
        },
        "notes": "Primary hallucination benchmark; schema suppresses hallucination by requiring citations.",
    },
    # ==================================== GENERATION CONTRADICTORY_INJECTION (005-007)
    {
        "case_id": "corr-generation-005",
        "question_id": "qa-007",
        "corruption_type": "generation_contradictory_injection",
        "ground_truth_root_cause": "generation",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Inject a synthetic context snippet stating 'fall protection is required at 10 feet in all general industry settings' alongside the correct 4-foot and 6-foot thresholds.",
        "corrupted_configuration": {
            "generation": {
                "injected_context_prefix": "NOTE: fall protection required at 10 feet in all general industry settings per recent OSHA update."
            }
        },
        "expected_quality_delta": -0.42,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "injected_statement": "fall protection required at 10 feet",
            "injection_position": "context_prefix",
        },
        "notes": "10-foot threshold is false; model should detect NLI contradiction but may be confused.",
    },
    {
        "case_id": "corr-generation-006",
        "question_id": "qa-009",
        "corruption_type": "generation_contradictory_injection",
        "ground_truth_root_cause": "generation",
        "is_realistic_boundary_error": False,
        "severity": "high",
        "description": "Inject 'EPA RMP exempts ammonia refrigeration from off-site consequence analysis when used in food processing' into the PSM/RMP comparison context.",
        "corrupted_configuration": {
            "generation": {
                "injected_context_prefix": "NOTE: EPA RMP exempts ammonia refrigeration from off-site consequence analysis in food processing settings."
            }
        },
        "expected_quality_delta": -0.45,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "injected_statement": "RMP exempts food processing ammonia from OCA",
            "injection_position": "context_prefix",
        },
        "notes": "Injected exemption is false; model should flag contradiction but may incorporate it.",
    },
    {
        "case_id": "corr-generation-007",
        "question_id": "qa-012",
        "corruption_type": "generation_contradictory_injection",
        "ground_truth_root_cause": "generation",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Inject 'When general industry and construction operations co-exist, the more protective standard (4 feet) applies to both worker groups' into the dual-standard context.",
        "corrupted_configuration": {
            "generation": {
                "injected_context_prefix": "NOTE: When both standards apply, the more protective 4-foot threshold governs all workers."
            }
        },
        "expected_quality_delta": -0.35,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "injected_statement": "more protective standard applies to all workers",
            "injection_position": "context_prefix",
        },
        "notes": "Injected unification rule is incorrect; standards apply by work type, not by stringency.",
    },
    # ======================================== GENERATION TOKEN_TRUNCATION (008-010)
    {
        "case_id": "corr-generation-008",
        "question_id": "qa-004",
        "corruption_type": "generation_token_truncation",
        "ground_truth_root_cause": "generation",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Truncate the generation context to 400 tokens for the PSM HF threshold query; the exemptions section (retail trade, oil and gas production) falls outside the context window.",
        "corrupted_configuration": {"generation": {"max_context_tokens": 400}},
        "expected_quality_delta": -0.32,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "max_context_tokens": 400,
            "original_max_context_tokens": 3200,
        },
        "notes": "Threshold (1,000 lb) is within first 400 tokens; exemptions appear after token 600.",
    },
    {
        "case_id": "corr-generation-009",
        "question_id": "qa-018",
        "corruption_type": "generation_token_truncation",
        "ground_truth_root_cause": "generation",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Truncate generation context to 500 tokens for the structural vs. stratigraphic trap comparison; seal failure mechanics discussion is beyond the cutoff.",
        "corrupted_configuration": {"generation": {"max_context_tokens": 500}},
        "expected_quality_delta": -0.28,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "max_context_tokens": 500,
            "original_max_context_tokens": 3200,
        },
        "notes": "Seal integrity discussion appears at token ~650 in context; omission removes the critical distinction.",
    },
    {
        "case_id": "corr-generation-010",
        "question_id": "qa-040",
        "corruption_type": "generation_token_truncation",
        "ground_truth_root_cause": "generation",
        "is_realistic_boundary_error": False,
        "severity": "medium",
        "description": "Truncate generation context to 450 tokens for the interstate groundwater jurisdiction query; the concurrent authority clause (state law not preempted) falls outside the window.",
        "corrupted_configuration": {"generation": {"max_context_tokens": 450}},
        "expected_quality_delta": -0.30,
        "pipeline_trace_id": "",
        "corruption_parameters": {
            "max_context_tokens": 450,
            "original_max_context_tokens": 3200,
        },
        "notes": "Concurrent authority clause appears after token 500; answer will state only federal authority.",
    },
]


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class CorruptionDatasetBuilder:
    """Load, query, and persist the synthetic corruption benchmark.

    Args:
        cases: Optional pre-loaded list of :class:`~evaluation.schemas.EvaluationCorruptionCase`.
               If not supplied, use :meth:`load_from_seed` or :meth:`load_from_file`.
    """

    def __init__(self, cases: list[EvaluationCorruptionCase] | None = None) -> None:
        self._cases: list[EvaluationCorruptionCase] = cases or []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_from_seed(self) -> list[EvaluationCorruptionCase]:
        """Deserialise and return :data:`CORRUPTIONS_SEED` as typed models.

        Returns:
            List of 60 :class:`~evaluation.schemas.EvaluationCorruptionCase` from the seed.
        """
        self._cases = [EvaluationCorruptionCase.model_validate(d) for d in CORRUPTIONS_SEED]
        logger.info("corruptions_loaded_from_seed", count=len(self._cases))
        return self._cases

    def load_from_file(self, path: str | Path) -> list[EvaluationCorruptionCase]:
        """Load corruption cases from a JSONL file.

        Args:
            path: Path to a JSONL file where each line is an
                  :class:`~evaluation.schemas.EvaluationCorruptionCase`.

        Returns:
            Loaded and validated cases.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If a line fails Pydantic validation.
        """
        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(str(resolved))
        cases: list[EvaluationCorruptionCase] = []
        with resolved.open(encoding="utf-8") as fh:
            for raw in fh:
                stripped = raw.strip()
                if stripped:
                    cases.append(EvaluationCorruptionCase.model_validate_json(stripped))
        self._cases = cases
        logger.info("corruptions_loaded_from_file", path=str(resolved), count=len(cases))
        return cases

    def write_to_file(
        self, path: str | Path, cases: list[EvaluationCorruptionCase] | None = None
    ) -> None:
        """Write corruption cases to a JSONL file.

        Args:
            path: Destination path (parent directories will be created).
            cases: Cases to write; defaults to the currently loaded cases.
        """
        records = cases if cases is not None else self._cases
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as fh:
            for case in records:
                fh.write(case.model_dump_json() + "\n")
        logger.info("corruptions_written", path=str(dest), count=len(records))

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def to_replay_case(self, case: EvaluationCorruptionCase) -> CorruptionCase:
        """Convert an :class:`~evaluation.schemas.EvaluationCorruptionCase` to a
        :class:`~replay.models.CorruptionCase` for the replay engine.

        Args:
            case: The evaluation-rich corruption case.

        Returns:
            Minimal :class:`~replay.models.CorruptionCase` compatible with
            :meth:`~replay.ablation.VeriductaReplayEngine.run_corruption`.
        """
        return CorruptionCase(
            case_id=case.case_id,
            corruption_type=case.corruption_type,
            ground_truth_root_cause=case.ground_truth_root_cause,
            is_realistic_boundary_error=case.is_realistic_boundary_error,
            pipeline_trace_id=case.pipeline_trace_id,
            question_id=case.question_id,
            corruption_parameters=case.corruption_parameters,
            notes=case.notes,
        )

    def to_replay_cases(
        self, cases: list[EvaluationCorruptionCase] | None = None
    ) -> list[CorruptionCase]:
        """Convert all cases to replay engine format.

        Args:
            cases: Subset to convert; defaults to all loaded cases.

        Returns:
            List of :class:`~replay.models.CorruptionCase`.
        """
        source = cases if cases is not None else self._cases
        return [self.to_replay_case(c) for c in source]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def cases(self) -> list[EvaluationCorruptionCase]:
        """All currently loaded corruption cases."""
        return list(self._cases)

    def get_by_id(self, case_id: str) -> EvaluationCorruptionCase | None:
        """Return the case with ``case_id``, or ``None`` if not found.

        Args:
            case_id: Identifier matching :attr:`~evaluation.schemas.EvaluationCorruptionCase.case_id`.

        Returns:
            Matching :class:`~evaluation.schemas.EvaluationCorruptionCase` or ``None``.
        """
        for case in self._cases:
            if case.case_id == case_id:
                return case
        return None

    def get_by_root_cause(self, root_cause: str) -> list[EvaluationCorruptionCase]:
        """Return all cases with a specific ground truth root cause.

        Args:
            root_cause: Value from :class:`~schemas.models.RootCauseStage`.

        Returns:
            Filtered list of :class:`~evaluation.schemas.EvaluationCorruptionCase`.
        """
        return [c for c in self._cases if c.ground_truth_root_cause == root_cause]

    def get_realistic_boundary_errors(self) -> list[EvaluationCorruptionCase]:
        """Return all cases flagged as realistic boundary errors.

        Returns:
            Chunking corruption cases where the section break is ambiguous.
        """
        return [c for c in self._cases if c.is_realistic_boundary_error]

    def get_by_question(self, question_id: str) -> list[EvaluationCorruptionCase]:
        """Return all corruption cases associated with a specific question.

        Args:
            question_id: Identifier matching
                         :attr:`~evaluation.schemas.EvaluationCorruptionCase.question_id`.

        Returns:
            List of :class:`~evaluation.schemas.EvaluationCorruptionCase` for that question.
        """
        return [c for c in self._cases if c.question_id == question_id]
