# Unified PDF and YouTube Knowledge Search

Moil Bot can search saved YouTube transcript records and local PDF reference documents through one function: `knowledge.unified_search.search_all_knowledge`.

## Where it looks

- YouTube: `knowledge/videos/processed_knowledge.json` (the existing processed transcript catalogue).
- PDFs: files ending in `.pdf` anywhere under `knowledge/documents/`, including subfolders.

Use `pdf_directory=` if your PDF files are stored in a different folder. The function returns source-aware results with `source_type`, title, snippet, score, and the source location. Video hits include their YouTube URL and video ID. PDF hits include the PDF path and one-based page number.

## Example

```python
from knowledge.unified_search import search_all_knowledge

results = search_all_knowledge("liquidity sweep", limit=10)
for result in results:
    print(result["source_type"], result["title"], result["location"])
    if result["page"] is not None:
        print("Page:", result["page"])
    print(result["snippet"])
```

If PDFs are in another folder:

```python
results = search_all_knowledge(
    "fair value gap",
    pdf_directory=r"C:\\Users\\vumil\\Documents\\MoilBotPDFs",
)
```

## Important limitations

- This searches text embedded in PDFs. Scanned/image-only PDFs require OCR before their text can be searched.
- PDF pages are read when a search is run, so very large document collections may need a persistent index/cache later.
- This is a knowledge retrieval feature; it does not connect to MT5 or execute trades.
