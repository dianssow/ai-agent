# ai-agent
Production-ready AI Sales &amp; Support Agent built with Model Context Protocol (MCP), Hybrid RAG (pgvector + Full-Text Search with RRF), PostgreSQL triggers, and local Ollama LLMs.

# Autonomous Sales & Technical Support Agent (MCP + Hybrid RAG)

An end-to-end agentic AI system built with the **Model Context Protocol (MCP 2.x)**, **PostgreSQL (`pgvector` + Full-Text Search)**, and local **Ollama** models (`qwen2.5:3b` & `nomic-embed-text`).

Designed to bridge deterministic transactional SQL operations (inventory lookups, category filtering, order placement with database triggers) and semantic troubleshooting/product discovery using **Reciprocal Rank Fusion (RRF)**.

---

## Architecture


flow
    User([User Query - EN / DE / FR]) --> Guardrail{Input Security Guardrail}
    Guardrail -- Blocked --> Reject([Safe Refusal])
    Guardrail -- Valid --> Client[MCP Client Orchestrator Reasoning Loop + Arg Sanitizer]
    
    Client <--> LLM[Ollama: qwen2.5:3b]
    Client <-->|stdio / JSON-RPC| Server[MCP Server: mcp 2.x]
    
    Tools [MCP Tool ]
        T1[get_product_by_name / category]
        T2[search_products_hybrid]
        T3[get_alternative_product]
        T4[place_order + Human Confirmation]
    end
    
    Server --> Tools
    T2 --> Embed[Ollama: nomic-embed-text]
    T1 & T2 & T3 & T4 --> DB[(PostgreSQL 18 + pgvector)]
    DB -->|AFTER INSERT Trigger| Audit[(Stock Decrement & Audit Logs)]
