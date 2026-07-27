# ACME Corp — AI-Powered Data Platform Architecture

## Overview

ACME Corp is a financial technology company that processes over 2 billion transactions per day across
40 countries. Their AI-powered data platform, codenamed **Project Atlas**, consists of six core
subsystems orchestrated by a central control plane called **Hermes**.

## Core Components

### 1. Ingestion Layer — Kafka Streams

All real-time data enters through a **Kafka** cluster running 64 brokers. The cluster is managed
by the **DataOps** team led by **Sarah Chen**. Topics are automatically created by the
**AutoSchema** service, which infers Avro schemas from incoming JSON payloads.

Key configurations:
- Retention: 72 hours for raw events, 30 days for enriched events
- Replication factor: 3 for all production topics
- Consumer groups: 18 active groups; the largest is `fraud-detection-cg` with 128 partitions

### 2. Feature Store — Feast + Redis

The **Feature Store** is built on **Feast** with **Redis** as the online store and **Apache Hive**
as the offline store. It is maintained by the **ML Platform** team led by **Dr. Marcus Rivera**.

Features are organized into 14 feature sets:
- `user_transaction_history` — rolling 30-day aggregate stats per user
- `merchant_risk_profile` — updated hourly from the **Compliance Engine**
- `device_fingerprint` — real-time signals from the **Identity Service**

The feature materialization pipeline runs on **Apache Spark** clusters provisioned via
**AWS EMR** in the `us-east-1` and `eu-west-1` regions.

### 3. Model Training — MLflow + Kubernetes

Model training is orchestrated by **MLflow** running on a **Kubernetes** cluster managed by
**ArgoCD**. The platform uses two primary model types:

- **Gradient Boosting** (LightGBM) for fraud classification — trained by **Elena Vasquez**
- **Transformer-based** (BERT fine-tuned) for transaction categorization — maintained by **James Park**

All experiments are tracked in the MLflow Model Registry. Production models require approval
from the **Risk Committee** chaired by **Dr. Aisha Okonkwo** before deployment.

### 4. Inference Layer — Triton + vLLM

Real-time inference runs on **NVIDIA Triton Inference Server** deployed across three GPU node pools.
The LLM workloads (GPT-4 fine-tuned for financial reasoning) run on **vLLM** with tensor parallelism
across 8× A100 GPUs.

Latency SLAs:
- Fraud scoring: P99 < 8ms
- Transaction categorization: P95 < 50ms
- LLM-based financial advice: P90 < 2 seconds

### 5. Observability — Prometheus + Grafana + OpenTelemetry

All services emit metrics to **Prometheus** scraped every 15 seconds. Dashboards are in **Grafana**
maintained by the **SRE team** led by **Tom Nakamura**. Distributed traces flow through
**OpenTelemetry** collectors into **Jaeger** for latency debugging.

Alerting uses **PagerDuty** with escalation policies defined per service tier:
- Tier 1 (fraud detection): 2-minute response SLA, on-call: **Carlos Mendoza**
- Tier 2 (analytics): 15-minute response SLA
- Tier 3 (reporting): next-business-day

### 6. Data Warehouse — Snowflake + dbt

The analytical layer is a **Snowflake** data warehouse with 480 TB of structured data.
**dbt** (data build tool) manages 1,200+ transformation models maintained by the **Analytics
Engineering** team under **Priya Sharma**.

Key datasets:
- `TRANSACTIONS_FACT` — 2.1 billion rows, partitioned by day and region
- `USER_DIM` — 340 million user profiles with PII masked via **Vault**
- `FRAUD_EVENTS` — enriched fraud signals joined with model predictions

## Relationships Between Components

- **Kafka → Feature Store**: The ingestion pipeline publishes enriched events to Feast
- **Feature Store → MLflow**: Training jobs pull historical features from Hive via Feast SDK
- **MLflow → Triton**: Approved models are exported to ONNX and deployed to Triton
- **Triton → Kafka**: Inference results are published back to Kafka for downstream consumers
- **Kafka → Snowflake**: The **Firehose** connector streams all events to Snowflake in near real-time

## Security and Compliance

All data at rest is encrypted with **AWS KMS** using CMK keys. Data in transit uses **mTLS**
enforced by the **Istio** service mesh. PII fields are tokenized by the **Vault** service managed
by the **Security** team led by **Fatima Al-Hassan**.

The platform is certified under **SOC 2 Type II**, **PCI DSS Level 1**, and **GDPR**. Audits are
conducted quarterly by external auditor **Deloitte**.

## Incident History

- **2024-03-15**: Kafka lag spike caused by AutoSchema hot-restart; 4-minute partial outage
  on fraud detection. Post-mortem written by **Sarah Chen** and **Carlos Mendoza**.
- **2024-06-02**: Snowflake compute credit exhaustion due to runaway dbt model; resolved by
  **Priya Sharma** in 45 minutes. Cost guardrails added.
- **2024-09-11**: vLLM OOM crash on A100 nodes during model reload; **James Park** added
  health-check grace period fix.
