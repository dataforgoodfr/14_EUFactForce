# Ground-Truth Editorial Standard

This file defines the normalization policy used for full-text fidelity scoring.
All files under `ground_truth/texts/` should follow these conventions.

## Purpose

- Keep benchmark comparisons fair across parser/pre/post-processing variants.
- Measure extraction quality, not formatting noise.
- Make new ground-truth additions consistent over time.

## Canonical Rules

- **Footnotes placement:** keep footnote content, but place footnotes at the end of the document body when source layout is mixed.
- **Footnote markers (superscripts/exponents):** use one convention consistently across a file (either keep markers or remove them), and prefer removing isolated markers when they add no semantic content.
- **Order policy:** preserve logical reading order of the article/report text.
- **No content deletion:** do not drop meaningful sentences/claims while normalizing.
- **Heading consistency:** keep heading hierarchy readable and stable (avoid arbitrary re-labeling).
- **Whitespace/line breaks:** normalize obvious OCR/parser artifacts, but do not rewrite meaning.

## Scoring Assumption

`quality_scoring.py` and `fidelity_optimization.py` evaluate extracted text against this normalized editorial style, not strict PDF-layout reproduction.

If conventions change, update this file and regenerate benchmark artifacts.
