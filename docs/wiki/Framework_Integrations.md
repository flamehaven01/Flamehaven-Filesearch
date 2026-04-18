# Framework Integrations (v1.5.0)

`flamehaven_filesearch.integrations` provides plug-and-play document loaders
and readers for popular AI agent frameworks. All adapters use FLAMEHAVEN's
internal extraction and chunking pipelines — no external document-AI framework
required.

Framework SDKs are imported lazily: install only what you use.

---

## LangChain

**Install:** `pip install langchain-core`

```python
from flamehaven_filesearch.integrations import FlamehavenLangChainLoader

# Single document → one LangChain Document
loader = FlamehavenLangChainLoader("report.pdf")
docs = loader.load()
# docs[0].page_content  → extracted text
# docs[0].metadata      → {"source": "report.pdf", "filename": "report.pdf"}

# Chunked → one Document per chunk
loader = FlamehavenLangChainLoader("report.pdf", chunk=True, max_tokens=512)
docs = loader.load()
# docs[i].metadata → {..., "headings": ["Introduction", "Background"], "chunk_index": i}

# Lazy loading (streaming)
for doc in loader.lazy_load():
    process(doc)
```

### With LangChain RAG pipeline

```python
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from flamehaven_filesearch.integrations import FlamehavenLangChainLoader

docs = FlamehavenLangChainLoader("report.pdf", chunk=True).load()
vectorstore = InMemoryVectorStore.from_documents(docs, OpenAIEmbeddings())
retriever = vectorstore.as_retriever()
```

---

## LlamaIndex

**Install:** `pip install llama-index-core`

```python
from flamehaven_filesearch.integrations import FlamehavenLlamaIndexReader

reader = FlamehavenLlamaIndexReader()
documents = reader.load_data(["report.pdf", "slides.pptx", "data.csv"])
# documents[i].text      → extracted text
# documents[i].metadata  → {"file_path": "...", "file_name": "..."}

# Chunked nodes
reader = FlamehavenLlamaIndexReader(chunk=True, max_tokens=512)
nodes = reader.load_data(["report.pdf"])
# nodes[i].metadata → {..., "headings": [...], "chunk_index": i}
```

### With LlamaIndex index

```python
from llama_index.core import VectorStoreIndex
from flamehaven_filesearch.integrations import FlamehavenLlamaIndexReader

documents = FlamehavenLlamaIndexReader(chunk=True).load_data(["report.pdf"])
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()
response = query_engine.query("What are the main findings?")
```

---

## Haystack

**Install:** `pip install haystack-ai`

```python
from flamehaven_filesearch.integrations import FlamehavenHaystackConverter

converter = FlamehavenHaystackConverter()
result = converter.run(sources=["report.pdf", "slides.pptx"])
documents = result["documents"]
# documents[i].content  → extracted text
# documents[i].meta     → {"file_path": "...", "file_name": "..."}

# Chunked
converter = FlamehavenHaystackConverter(chunk=True, max_tokens=512)
result = converter.run(sources=["report.pdf"])
```

### With Haystack pipeline

```python
from haystack import Pipeline
from haystack.components.writers import DocumentWriter
from haystack.document_stores.in_memory import InMemoryDocumentStore
from flamehaven_filesearch.integrations import FlamehavenHaystackConverter

store = InMemoryDocumentStore()
pipeline = Pipeline()
pipeline.add_component("converter", FlamehavenHaystackConverter(chunk=True))
pipeline.add_component("writer", DocumentWriter(document_store=store))
pipeline.connect("converter.documents", "writer.documents")
pipeline.run({"converter": {"sources": ["report.pdf"]}})
```

---

## CrewAI

**Install:** `pip install crewai`

```python
from flamehaven_filesearch.integrations import FlamehavenCrewAITool

tool = FlamehavenCrewAITool()
# tool.name        → "FlamehavenFileParser"
# tool.description → shown to the LLM agent

# Direct call
text = tool.run("report.pdf")

# Async
text = await tool._arun("report.pdf")
```

### With CrewAI agent

```python
from crewai import Agent, Task, Crew
from flamehaven_filesearch.integrations import FlamehavenCrewAITool

analyst = Agent(
    role="Document Analyst",
    goal="Extract and analyze document content",
    tools=[FlamehavenCrewAITool()],
    llm="gpt-4o",
)

task = Task(
    description="Read report.pdf and summarize the key findings.",
    agent=analyst,
    expected_output="A concise bullet-point summary.",
)

crew = Crew(agents=[analyst], tasks=[task])
crew.kickoff()
```

---

## Supported Formats

All adapters support every format that `extract_text()` handles:

| Format | Extension(s) | Notes |
|---|---|---|
| PDF | `.pdf` | `[parsers]` extra |
| Word | `.docx` `.doc` | `[parsers]` extra |
| Excel | `.xlsx` `.xlsm` | `[parsers]` extra |
| PowerPoint | `.pptx` `.ppsx` | `[parsers]` extra |
| RTF | `.rtf` | `[parsers]` extra |
| HTML | `.html` `.htm` | stdlib, no extra |
| WebVTT | `.vtt` | stdlib, no extra |
| LaTeX | `.tex` `.latex` | stdlib, no extra |
| CSV | `.csv` | stdlib, no extra |
| Markdown / Text | `.md` `.txt` | stdlib, no extra |
| Image (OCR) | `.jpg` `.png` `.tiff` | `[vision]` extra |
