# Ground-Truth Editorial Standard

This file defines the normalization policy used for full-text fidelity scoring.
All files under `ground_truth/texts/` should follow these conventions.

## Purpose

- Keep benchmark comparisons fair across parser/pre/post-processing variants.
- Measure extraction quality, not formatting noise.
- Make new ground-truth additions consistent over time.

## Canonical Rules

- **Footnotes placement:** footnote content is kept, and in mixed layouts it is placed at the end of the main document body.
- **Footnote markers (superscripts/exponents):** each file uses one consistent marker convention; isolated markers that do not add semantic value are typically removed.
- **Reference scrutiny:** reference sections do not benefit from the same scrutiny as the content since they are excluded from the comparison scoring.
- **Order policy:** text is organized to reflect logical reading order of the article/report content.
- **Content preservation:** meaningful sentences and claims are preserved during normalization.
- **Heading consistency:** headings are kept readable and stable, without arbitrary relabeling. Heading hierarchy is not conserved at this moment.
- **Whitespace/line breaks:** obvious OCR/parser spacing artifacts are normalized while preserving meaning.
- **Figure handling:** when figures are encountered, they are represented as bracketed legend placeholders (for example, `[Figure 1: ...]`) rather than attempting to reconstruct image text content.
- **Table handling:** When possible, tables are kept, they are easier to handle and reproduce as Markdown.
    - Problem with tables is when cells are merged, this is difficult to reproduce as markdown.

## Scoring Assumption

`quality_scoring.py` and `fidelity_optimization.py` evaluate extracted text against this normalized editorial style, not strict PDF-layout reproduction.

If conventions change, update this file and regenerate benchmark artifacts.
