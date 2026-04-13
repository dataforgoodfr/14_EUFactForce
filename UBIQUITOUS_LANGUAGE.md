# Ubiquitous Language

Glossary for the **ingestion spine** (canonical document, files, lineage, parsing, chunks) as discussed for EU Fact Force. Terms align with `docs/prd-canonical-document.md` where applicable.

## Core aggregates

| Term | Definition | Aliases to avoid |
|------|------------|------------------|
| **Document** | The canonical database record for a logical publication or report, holding normalized bibliographic and product-facing metadata. | Paper, article (as table name), ResearchPaper |
| **SourceFile** | The stored binary artifact for an ingested file (e.g. PDF blob and storage key), separate from canonical metadata. | File (alone), upload row, S3 object (when meaning the DB row) |
| **IngestionRun** | One end-to-end ingestion attempt, capturing lineage: input, provider, status, stage, errors, and pipeline version. | Job (unless explicitly a background job), pipeline run (unless disambiguated) |
| **ParsedArtifact** | One persisted parse of a **Document**’s file content: raw Docling export, postprocessed text, extracted metadata snapshot, and parser config for that attempt. | Parse output (vague), “the parse” (use **ParsedArtifact** or **current parse**) |
| **DocumentChunk** | One searchable segment of text derived from a **ParsedArtifact**, ordered and optionally embedded for retrieval. | Chunk (in code comments only if clear), element (legacy) |

## Ingestion lifecycle

| Term | Definition | Aliases to avoid |
|------|------------|------------------|
| **Run status** | Terminal or in-progress state of an **IngestionRun**: `running`, `success`, or `failed`. | State (alone), outcome (prefer **success kind** for full vs metadata-only) |
| **Run stage** | The last completed or active step in the run’s progression (e.g. acquire, store, parse, map_metadata, chunk, embed, done). | Phase (unless synonymous), step number |
| **Success kind** | When **Run status** is `success`, whether the run completed the full file pipeline (`full`) or stopped after metadata without a storable file (`metadata_only`). | Partial success (use **metadata_only**), soft success |
| **Acquisition** | Obtaining a file and/or metadata from user input or external systems before or alongside storage. | Fetch (when it includes metadata-only paths) |
| **map_metadata** | The step that writes normalized fields on **Document** using merge rules, typically field-by-field from provider vs parsing sources. | Enrichment (too broad), sync |

## Metadata & provenance

| Term | Definition | Aliases to avoid |
|------|------------|------------------|
| **Provider** | The external system or integration that returns bibliographic or file data (e.g. DOI resolver, publisher API). | API (alone), upstream (vague) |
| **Raw provider payload** | Verbatim response body from a **Provider**, kept for audit and reprocessing. | Cached JSON (unless clearly this row), normalized metadata |
| **Normalized field** | A value stored on **Document** after **map_metadata**, intended as the product-facing canonical value for that attribute. | Final value (without naming **Document**) |
| **metadata_extracted** | Structured metadata inferred from parsing, stored on **ParsedArtifact**, used as fallback input to **map_metadata** and for conflict audit. | Parsed meta (vague), sidecar |
| **Postprocessing** | Transformations applied after Docling conversion (e.g. hierarchical postprocessor, markdown normalization, bbox validation) before the **Processed text** is final. | Cleaning (too vague) |
| **Processed text** | The text string after Docling plus all agreed postprocessing, ready for chunking. | Final markdown (if other formats exist) |
| **Pipeline version** | A version identifier for the ingestion executable logic, recorded on **IngestionRun** for support and comparison across attempts. | Git SHA (unless that is what you store), build id (unless defined as this) |

## Relationships

- A **Document** may link to zero or one **SourceFile** (metadata-only vs file-attached).
- An **IngestionRun** may reference a **Document** and/or a **SourceFile** as they become available during the attempt.
- Many **ParsedArtifact** rows may belong to one **Document**; the **current parse** is the latest **ParsedArtifact** by `created_at` unless a future flag overrides that rule.
- Each **DocumentChunk** belongs to exactly one **ParsedArtifact**, which belongs to exactly one **Document**.
- **map_metadata** reads from **Provider** responses and **metadata_extracted** (and analogous sources) and writes **Normalized field** values on **Document**.

## Example dialogue

> **Dev:** “We created an **IngestionRun** for a DOI; **Run status** is still `running` at **Run stage** `acquire`. Do we already have a **Document**?”  
> **Domain expert:** “Yes, we can have a **Document** with the DOI set even before a **SourceFile** exists. If no PDF is storable, we end with **Success kind** `metadata_only` and never create a **ParsedArtifact**.”  
> **Dev:** “When the PDF exists, we add **SourceFile**, then one **ParsedArtifact**, then **DocumentChunk** rows. If the **Provider** title differs from **metadata_extracted**, what wins on **Document**?”  
> **Domain expert:** “For each **Normalized field**, if the **Provider** value is non-empty it wins; otherwise we use **metadata_extracted**. We keep the parsing side in **metadata_extracted** for audit.”  
> **Dev:** “User re-uploads and we parse again—two **ParsedArtifact** rows?”  
> **Domain expert:** “Yes. Chunks always point to the **ParsedArtifact** that produced them; we treat the newest **ParsedArtifact** as **current parse** for default retrieval unless we add an explicit flag later.”

## Flagged ambiguities

- **“Run”** can mean **IngestionRun** (DB row) or an informal “pipeline execution”—in docs and APIs prefer **IngestionRun** or **ingestion attempt**.
- **“API”** sometimes means HTTP surface, sometimes **Provider**—prefer **Provider** when talking about the source of bibliographic or file data.
- **“Parse”** as a verb vs **ParsedArtifact** as a noun: say **parsing** for the activity and **ParsedArtifact** for the stored row.
- **“Document”** in product language (PDF file) vs **Document** the aggregate—in backend discussions use **SourceFile** for the blob and **Document** for the canonical record.
