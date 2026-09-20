# Corpus design

The TD RagBot corpus (4,979 chunks, ~287 source files: TouchDesigner wiki, forum threads, an introductory book, several GitHub repositories) was built for Q&A retrieval — hybrid search (`all-MiniLM-L6-v2` embeddings + BM25, RRF fusion), answering natural-language questions about TouchDesigner.

The td-agent project needs a second, structurally different corpus: not prose to answer questions from, but **verified technique documents** the agent can retrieve *and act on* — see [[midi system ingestion (planned)]].

**Related:** [[../05 Roadmap|Roadmap]] item 6
