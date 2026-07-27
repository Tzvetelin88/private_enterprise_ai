# Vector Search Internals: From Embeddings to Approximate Nearest Neighbours

## What Is a Vector Embedding?

A **vector embedding** is a dense numerical representation of an object (text, image, audio)
in a high-dimensional space. Objects that are semantically similar end up geometrically close.

For example, the sentence "A dog ran across the field" and "The canine sprinted through the meadow"
will have embeddings with a **cosine similarity** close to 1.0, while "Stock market crash" will
produce an embedding far away from both.

## Embedding Models

### Sentence Transformers (SBERT)

**Sentence-BERT** (SBERT) was introduced by Nils Reimers and Iryna Gurevych in 2019. It modified
the original BERT architecture to produce fixed-size sentence embeddings using a Siamese network
structure trained with contrastive loss.

Popular SBERT models:
- `all-MiniLM-L6-v2` — 384 dimensions, very fast, best for general English
- `BAAI/bge-large-en-v1.5` — 1024 dimensions, MTEB leaderboard top performer
- `intfloat/e5-mistral-7b-instruct` — 4096 dimensions, uses a 7B LLM as encoder

### Proprietary Models

- **OpenAI `text-embedding-3-large`** — 3072 dimensions, supports dimension reduction via Matryoshka
- **Cohere Embed v3** — natively multimodal, supports 100+ languages
- **Google Gecko** — powers Google's Vertex AI Vector Search

## Approximate Nearest Neighbour (ANN) Algorithms

Exact nearest-neighbour search over millions of vectors requires O(N) comparisons per query.
ANN algorithms trade a small recall loss for dramatic speed improvements.

### HNSW (Hierarchical Navigable Small World)

HNSW was introduced by Yury Malkov and Dmitry Yashunin in 2016. It builds a multi-layer graph
where upper layers have long-range "express" connections and the bottom layer has fine-grained
short-range connections.

Key parameters:
- `M` — number of bidirectional links per node (default 16). Higher M = more accurate, more memory
- `ef_construction` — size of dynamic candidate list during build (default 200)
- `ef_search` — candidate list size at query time; controls accuracy/speed tradeoff

Performance characteristics:
- Build time: O(N × M × log N)
- Query time: O(log N) amortized
- Memory: ~(M × 8 + 100) bytes per vector for 1024-dim float32

### IVF-PQ (Inverted File Index + Product Quantization)

IVF-PQ, popularized by **Facebook AI (FAISS)**, combines two techniques:
1. **IVF** — clusters vectors into Voronoi cells using K-means; at query time only `nprobe` cells
   are searched, reducing comparisons from N to approximately N/nlist
2. **PQ (Product Quantization)** — compresses each vector by splitting it into M sub-vectors,
   each quantized independently. Achieves 8-32× memory reduction at the cost of some accuracy.

FAISS is maintained by **Herve Jegou** and the **Meta AI** team and is the foundation of many
production vector search systems.

### ScaNN (Scalable Nearest Neighbours)

Developed by **Google Research** (Ruiqi Guo et al., 2020), ScaNN introduces **anisotropic vector
quantization** — a quantization scheme that prioritises preserving inner product accuracy for
vectors that are likely to be nearest neighbours.

Benchmark results on the **ann-benchmarks.com** GLUE dataset show ScaNN achieving ~0.98 recall
at 2,000 QPS per CPU core.

## Vector Databases

### pgvector (PostgreSQL Extension)

**pgvector** was created by **Andrew Kane** and integrates seamlessly into PostgreSQL.
It supports three distance metrics: **L2 distance**, **cosine distance**, and **inner product**.

Index types supported:
- `ivfflat` — faster build, lower accuracy; partition count set at build time
- `hnsw` — added in pgvector 0.5.0; better recall, incremental insertions supported

A typical production setup uses `hnsw` with `m=16, ef_construction=64` for the index, and
`SET hnsw.ef_search = 100` per session for high-recall queries.

### Pinecone

**Pinecone** is a fully managed vector database founded by **Edo Liberty** (former head of
Amazon AI Labs). It uses a proprietary ANN algorithm called **Pinecone Hierarchical Navigable
Graph (PHNG)** and supports real-time upserts with ACID guarantees at the pod level.

Namespaces allow logical partitioning within a single index — useful for multi-tenancy.

### Weaviate

**Weaviate** (originally developed by **SeMI Technologies**, now Weaviate B.V.) supports
both vector search and keyword (BM25) search with automatic hybrid fusion. Its graph-like
data model uses "Classes" and "Properties" analogous to RDF triples, enabling knowledge graph
queries alongside semantic search.

### Qdrant

**Qdrant** (written in Rust by **Andrey Vasnetsov** and team) is notable for its support of
**sparse vectors**, **quantization modes** (binary, scalar, product), and **payload filtering**
at query time without pre-filtering overhead. It uses a modified HNSW implementation with
filterable HNSW for efficient filtered ANN search.

## Hybrid Search: Dense + Sparse

Pure semantic search can miss keyword-heavy queries (product IDs, names, codes). **Hybrid search**
combines dense vector search with **BM25** (Best Match 25), a probabilistic keyword scoring
function derived from the Okapi BM25 model.

Fusion strategies:
- **RRF (Reciprocal Rank Fusion)** — score = Σ 1/(k + rank_i) across ranked lists; k=60 is typical
- **Linear interpolation** — score = α × dense_score + (1-α) × sparse_score; α tuned on validation set
- **Cross-encoder reranking** — a small BERT-based model rescores top-100 candidates from first stage

## Matryoshka Representation Learning (MRL)

MRL (introduced by **Kusupati et al.** at **UW / Google**, 2022) trains embedding models so that
the first d dimensions form a valid embedding of quality proportional to d. This means you can
truncate a 1536-dim embedding to 256 dims and still get ~90% of the recall, reducing storage
and compute costs by 6×.

OpenAI's `text-embedding-3` series uses MRL, allowing users to specify `dimensions` at inference
time (e.g., 512 instead of 3072) with graceful quality degradation.

## Evaluation Metrics

- **Recall@k** — fraction of true nearest neighbours found in top-k results; industry standard is R@10
- **NDCG@10** — Normalized Discounted Cumulative Gain; rewards relevant results at higher ranks
- **QPS (Queries Per Second)** — throughput at a fixed recall target (typically R@10 ≥ 0.95)
- **Build time** and **Index size** — infrastructure cost proxies
