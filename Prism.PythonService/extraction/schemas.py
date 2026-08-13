"""Pydantic schemas for the claim extraction pipeline.

Two-layer design:
  - LLM layer: what Gemini produces via structured output.
    NEVER contains grounding_status, missing, or reason.
  - Final layer: what the pipeline writes to Postgres.
    LLM fields + grounding fields set by the audit stage.

Enum values match the C# HasConversion<string>() serialization
in Prism.ApiService/Data/Schemas/ so Python writes cleanly to
paper_claims and its jsonb-owned EvidenceSpans column.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ClaimLabel(str, Enum):
    """Claim grounding strength as judged by the LLM extractor."""
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    NOT_SUPPORTED = "not_supported"


class GroundingStatus(str, Enum):
    """Grounding pipeline verdict - set by pipeline, NOT by LLM.

    Values match C# GroundingStatus enum HasConversion<string>()
    which serializes as PascalCase enum member names.
    """
    PASS = "Pass"
    FAIL = "Fail"
    SKIPPED = "Skipped"


# --- LLM layer ---

class EvidenceSpanLLM(BaseModel):
    """One evidence quote from the paper backing up a claim.

    Filled by the LLM during extraction. No grounding_status yet.
    """

    source_text: str = Field(
        ...,
        description="Exact quote from the paper (verbatim, character-for-character)"
    )
    source_section: str = Field(
        ...,
        description="Where the quote appears, e.g. 'Table 1' or 'Section 4.3'"
    )
    section_header: Optional[str] = Field(
        None,
        description="Fuller section title if available, e.g. '4.3 HumanEval Results'"
    )
    page_number: Optional[int] = Field(
        None,
        description="Page number in the PDF if inferable, else null"
    )


class ClaimLLM(BaseModel):
    """One claim extracted from the paper.

    Filled by the LLM. Grounding fields set later by the pipeline.
    """

    claim_text_verbatim: str = Field(
        ...,
        description="Exact text of the claim as it appears in the paper"
    )
    claim_summary: str = Field(
        ...,
        description="10-15 word rephrasing for the Claim-Support Matrix UI"
    )
    label: ClaimLabel = Field(
        ...,
        description="LLM's assessment of grounding strength based on visible evidence"
    )
    evidence_spans: list[EvidenceSpanLLM] = Field(
        ...,
        min_length=1,
        description="At least one evidence span. Multiple if claim is backed by multiple sources."
    )


class ClaimsExtractionResponse(BaseModel):
    """Top-level Gemini structured output response.

    Contains a list of claims. Empty list is valid when the paper
    has no groundable empirical claims - this is the correct-refusal
    signal at extraction time.
    """

    claims: list[ClaimLLM] = Field(
        ...,
        description="All empirical claims extracted from the paper. Empty if none groundable."
    )


# --- Final layer (pipeline-finalized, written to Postgres) ---

class EvidenceSpanFinal(BaseModel):
    """EvidenceSpan with pipeline-appended grounding_status."""
    model_config = ConfigDict(extra="forbid")

    source_text: str
    source_section: str
    section_header: Optional[str] = None
    page_number: Optional[int] = None
    grounding_status: GroundingStatus


class ClaimFinal(BaseModel):
    """Claim with pipeline-appended grounding fields.

    This is the shape written to paper_claims table.
    """
    model_config = ConfigDict(extra="forbid")

    claim_text_verbatim: str
    claim_summary: str
    label: ClaimLabel
    evidence_spans: list[EvidenceSpanFinal]

    # Pipeline-set fields
    grounding_status: GroundingStatus
    missing: bool = False
    reason: Optional[str] = None


# --- Metadata extraction (Prompt 1) - LLM layer ---

class PaperMetadataLLM(BaseModel):
    """Paper-level metadata filled by the LLM extractor from Prompt 1.

    Empty strings are valid - the prompt instructs the LLM to return an
    empty string when a field's information is not present in the paper,
    rather than fabricate it.
    """

    research_objective: str = Field(
        ...,
        description="Primary research goal, one sentence, from the Abstract/Introduction"
    )
    headline_conclusion: str = Field(
        ...,
        description="The paper's main finding in one sentence"
    )
    sample_characteristics: str = Field(
        ...,
        description="Datasets, benchmarks, tasks, or subjects evaluated on, with sizes if reported"
    )
    baselines_compared: str = Field(
        ...,
        description="Alternative methods, models, or approaches the paper compared against"
    )
    ablation_studies: str = Field(
        ...,
        description="Component-removal experiments and what was learned; 'None reported' if none"
    )
    experimental_confounds: str = Field(
        ...,
        description="Conditions that might complicate interpretation of results; 'None apparent' if none"
    )
    author_acknowledged_limitations: str = Field(
        ...,
        description="Limitations the authors themselves call out"
    )
    extrapolated_implications: str = Field(
        ...,
        description="Broader claims the paper makes about what its results mean for the field"
    )
    empirical_results: str = Field(
        ...,
        description="High-level summary of the numerical/empirical results"
    )


class MetadataExtractionResponse(BaseModel):
    """Top-level Gemini structured output response schema for Prompt 1.

    Passed as response_schema to Gemini's structured output config when
    extracting paper-level metadata.
    """

    metadata: PaperMetadataLLM = Field(
        ...,
        description="The 9 paper-level metadata fields extracted from the paper"
    )


# --- Metadata extraction (Prompt 1) - Final layer (pipeline-finalized) ---

class PaperMetadataFinal(BaseModel):
    """PaperMetadataLLM with pipeline-appended provenance fields.

    This is the shape written to document_extractors.Fields as jsonb.
    """
    model_config = ConfigDict(extra="forbid")

    research_objective: str
    headline_conclusion: str
    sample_characteristics: str
    baselines_compared: str
    ablation_studies: str
    experimental_confounds: str
    author_acknowledged_limitations: str
    extrapolated_implications: str
    empirical_results: str

    # Pipeline-set fields
    prompt_version: str
    model_used: str
    extracted_at: datetime
