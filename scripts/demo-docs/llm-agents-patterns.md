# LLM Agent Design Patterns

## What Is an LLM Agent?

An **LLM agent** is a system in which a large language model acts as a reasoning engine that
decides what actions to take, executes those actions (via tools or APIs), observes the results,
and iterates until a goal is achieved. Unlike a simple prompt-response chain, agents maintain
state across multiple steps and can use tools like web search, code execution, or database queries.

The term was popularized by the **ReAct** paper (Yao et al., 2022, Google Brain / Princeton),
which showed that interleaving reasoning traces ("Thought") with actions ("Action") dramatically
improved task performance on WebGPT-style benchmarks.

## Core Agentic Patterns

### 1. ReAct (Reasoning + Acting)

The **ReAct** loop consists of three alternating steps repeated until completion:
1. **Thought** — the LLM reasons about the current state and what to do next
2. **Action** — the LLM selects a tool and provides its input
3. **Observation** — the tool result is appended to context, and the loop continues

Strengths: simple, interpretable, works with any tool-use LLM.
Weaknesses: sequential — cannot parallelise multiple tool calls; no explicit planning.

### 2. Plan-and-Execute

Introduced by **LangChain** team (Harrison Chase) and formalized by **Plan-and-Solve** paper
(Wang et al., 2023). The agent first generates a complete plan (a list of sub-tasks), then
executes each step in order, potentially revising the plan as observations arrive.

Used in Microsoft's **TaskWeaver** and in **AutoGPT**-style systems.

### 3. Reflexion (Self-Critique)

**Reflexion** (Shinn et al., 2023, Northeastern University) adds a critic loop: after each
complete episode, a separate "reflector" LLM call identifies what went wrong and generates
a verbal critique stored in a long-term memory buffer. Future episodes start with these
critiques in context, effectively allowing the agent to learn from mistakes across trials
without gradient updates.

### 4. Tree of Thoughts (ToT)

**Tree of Thoughts** (Yao et al., 2023) treats problem solving as a tree search. At each step,
the LLM generates k candidate "thoughts" (partial solutions), a value function evaluates them,
and the search continues from the most promising branches using BFS or MCTS-style exploration.

Used in mathematical reasoning and game-playing benchmarks (24-game, crosswords).

### 5. Multi-Agent Systems

Multi-agent frameworks split work across specialised sub-agents that communicate via messages:

- **AutoGen** (Microsoft, **Chi Wang** and team) — agents exchange messages in a conversation;
  a "GroupChat" manager routes messages between a planner, coder, and critic.
- **CrewAI** (João Moura) — roles-based crew with YAML-defined task delegation
- **LangGraph** (LangChain team) — models agent workflows as directed cyclic graphs (DCGs) using
  a **StateGraph** abstraction; supports human-in-the-loop checkpoints.

LangGraph is particularly suited for **self-correcting RAG** pipelines because its conditional
edges can route back to retrieval if the grader node deems retrieved documents irrelevant.

## Tool Use and Function Calling

Modern LLMs (GPT-4, Claude 3, Gemini) support **structured function calling**: the model outputs
a JSON blob specifying which function to call and its arguments, rather than free-form text.

The **Model Context Protocol (MCP)** standardises tool definitions so that any MCP-compatible
host can discover and call tools from any MCP server without bespoke integrations. MCP was
introduced by **Anthropic** in November 2024 and rapidly adopted by IDE vendors (Cursor, Windsurf,
JetBrains) and data tool companies (Zapier, Databricks, Cloudflare).

An MCP server exposes a `tools/list` endpoint returning a JSON schema per tool. The LLM host
fetches this catalog, injects it into the system prompt, and intercepts the model's tool-call
outputs to dispatch the right server.

## Memory Architecture

Agents use multiple memory tiers:

| Memory Type | Storage | Scope |
|---|---|---|
| **In-context** (working memory) | LLM context window | Single conversation |
| **External key-value** | Redis / DynamoDB | Cross-session recall |
| **Vector store** (episodic) | pgvector / Pinecone | Semantic retrieval |
| **Knowledge graph** (semantic) | Neo4j / Kuzu | Structured relationships |
| **Procedural** (fine-tuning) | Model weights | Permanent / expensive |

The **MemGPT** paper (Packer et al., 2023, UC Berkeley) proposes a virtual context manager
that pages memories in and out of the finite context window analogously to OS virtual memory,
enabling agents with effectively unlimited memory.

## Evaluation Frameworks

- **AgentBench** (Liu et al., 2023) — 8 real-world environments including web browsing,
  database manipulation, and household tasks
- **GAIA** (Meta AI / HuggingFace) — questions requiring multi-step tool use; GPT-4 with
  plugins achieves ~30%, humans ~92%
- **SWE-bench** — evaluates agents on real GitHub issues; Claude 3.5 Sonnet achieved 49% with
  the **SWE-agent** framework
- **τ-bench** (Sierra AI) — customer service agent evals with 50-turn conversations

## Safety and Alignment Concerns

Autonomous agents introduce novel risks:
- **Prompt injection** — malicious content in tool outputs hijacks agent behaviour
  (studied by **Riley Goodside**, **Kai Greshake** et al.)
- **Goal misgeneralisation** — agent pursues proxy goal instead of true objective in novel env
- **Cascading failures** — multi-agent systems can amplify a single agent's mistake
- **Irreversible actions** — sending emails, deleting files, making API calls that cannot be undone

**Principal hierarchy** (Anthropic) and **Constitutional AI** provide partial mitigations.
The **OWASP Top 10 for LLM Applications** (v1.1) lists prompt injection as the #1 risk.
