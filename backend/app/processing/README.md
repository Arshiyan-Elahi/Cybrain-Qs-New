# Layout-aware document ingestion

Pipeline:

```text
upload → classify → format extract → normalize → extraction QA → chunk
```

| Stage | Module | Notes |
| --- | --- | --- |
| Classify | `pipeline.classify_source`, `pdf_parser.classify_pdf_pages` | pdf/docx; digital/mixed/scanned |
| DOCX | `docx_parser` | python-docx + multi-signal headings |
| PDF | `pdf_parser` | Docling if installed, else pypdf |
| OCR | `ocr` | Pluggable; default `NullOcrProvider` |
| Normalize | `normalizer` | Furniture, appendix/revision, heading paths |
| QA | `qa` | Explicit PASS / WARNING / FAILED |
| Chunk | `chunker` | Structure-aware; atomic tables |

Public API: `extract()` / `ExtractedDocument` remain stable for ingestion.

## Production OCR / Docling

- Prefer **Docling** for layout-aware PDF when the runtime can host it
  (`pip install docling`). It is optional and auto-detected.
- Register a layout-preserving OCR provider via `set_ocr_provider(...)`.
  Recommended engines: Docling OCR, Tesseract/ocrmypdf with layout output.
- Do not OCR pages that already have a reliable text layer.
