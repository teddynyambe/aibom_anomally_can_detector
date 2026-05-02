# AIBOM Demonstrator: a CAN-bus AI Application

Companion repository for the paper

> **Enabling AI Bills of Materials Through Graph-Structured Metadata: A Model-Based Systems Engineering Approach**
> Teddy Nyambe, Maria DiValentin, Jeremy Daily — Colorado State University, Department of Systems Engineering

## What this repo is for

The paper proposes an MBSE-driven, graph-structured metadata model that unifies AI-related artifacts — datasets, models, configurations, runtime components, and provenance — inside a single knowledge graph. That graph is the source of truth from which an **AI Bill of Materials (AIBOM)** is generated, aligned with the SPDX 3.0 AI profile and the CycloneDX ML-BOM extension.

**The contribution of the paper is the metadata model and the AIBOM generation workflow, not the ML model in this repo.** What lives here is a deliberately small AI application — a J1939 CAN-bus classifier — chosen so the entire AI lifecycle (data collection, labelling, training, registration, inference, tool invocation) can be reproduced end-to-end on commodity hardware. As you walk through that lifecycle, every step emits the metadata artifacts that the AIBOM tooling harvests.

In other words: the model is the *test case*; the AIBOM is the *output*.

## How this repo maps to the paper's lifecycle

The paper's block definition diagram (Fig. 1) and activity diagram (Fig. 3) decompose any AI-enabled system into five lanes. Each lane in this repo produces metadata that an AIBOM generator indexes:

| Lane (paper) | Activities | Artifacts in this repo | Metadata harvested |
| --- | --- | --- | --- |
| **Data** | Source → Label/curate → Partition → Dataset vN | `data.csv` | Schema, row count, label distribution, content hash, source bus/PGN |
| **Training** | Preprocess → Train step → Evaluate → Register | `train_model.ipynb` | Feature-extraction logic, hyperparameters, library versions, training environment |
| **Registry** | Model vN | `model.joblib` | Algorithm class, training-data lineage, fitted weights, hash |
| **Inference** | Receive → Encode → Run → Decode → Final reply | `run_detector.py` | Feature-vector contract, deployment target, bus configuration |
| **Tools** | Read tool / Write tool decision gate | `python-can` bus interface, `cansend` injectors | Tool type (read vs write), authorisation context, real-world side effects |

When the AIBOM framework is pointed at the repository plus the running deployment, each row above becomes one or more nodes in the knowledge graph, with provenance edges connecting them across lanes.

## The chosen AI application

To exercise the full lifecycle, the repo trains a `RandomForestClassifier` to flag anomalous **J1939 Address Claim** messages on a CAN bus.

In SAE J1939, every Electronic Control Unit (ECU) broadcasts an Address Claim (PGN `0x00EEFF`, full ID `18EEFF00`) on power-up to claim a source address. The 8-byte payload carries the ECU's 64-bit **NAME**. A NAME of all zeros is invalid by the standard and is symptomatic of a malformed, spoofed, or compromised address-claim frame. The classifier learns to separate well-formed Address Claims from the all-zero-NAME case using a small labelled dataset.

The classifier is intentionally simple: enough to exercise data, training, registry, inference, and a tool invocation (transmitting on the bus), with no extraneous engineering that would obscure the AIBOM mapping above.

## Repository layout

| Path | Purpose |
| --- | --- |
| `data.csv` | Labelled training split — `timestamp, can_id, data, label`. |
| `test_data.csv` | Labelled test split with unseen source addresses. |
| `train_model.ipynb` | Feature extraction + `RandomForestClassifier` training; emits `model.joblib`. |
| `model.joblib` | Pre-trained model committed for convenience. |
| `run_detector.py` | Loads `model.joblib`, opens `socketcan` on `can0`, predicts per frame. |
| `requirements.txt` | Python runtime dependencies. |
| `aibom/interfaces.yaml` | Formal contracts for each metadata Interface (Data IF, Training IF, Registry IF, Inference IF, Tool IF) shown in the system IBD. |
| `aibom/aibom.ttl` | RDF/Turtle knowledge graph for this demonstrator. Triples are grouped by the IF that exposes them via the `aibom:exposedVia` predicate. |
| `aibom/aibom.cdx.json` | CycloneDX 1.6 ML-BOM rendered from the same graph — the standards-aligned AIBOM artifact. |

### Feature-vector contract

Both training and inference must use the same three features, in this order:

1. `source_address` — low byte of the 29-bit CAN ID (J1939 SA field).
2. `is_zero_name` — `1` if the 8-byte payload is `0000000000000000`, else `0`.
3. `timestamp` — inter-frame timing; trained from the CSV column, fixed to `0` at inference.

If you change the feature set, change it in **both** `train_model.ipynb` and `run_detector.py`. (This contract is itself one of the metadata facts the AIBOM records.)

## Reproducing the demonstrator

### Hardware

- Raspberry Pi 3B+ or newer (any Linux host with SocketCAN works).
- A CAN HAT — PiCAN2, Waveshare RS485-CAN-HAT, or any MCP2515-based board.
- A second CAN node to inject frames — another Pi, a USB-CAN adapter, or a J1939 simulator. For pure software experimentation you can use the kernel `vcan` (virtual CAN) module instead.

### 1. Clone and install

```bash
git clone https://github.com/teddynyambe/aibom_anomally_can_detector.git
cd aibom_anomally_can_detector
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Bring up the CAN interface

For real hardware running J1939 (250 kbit/s):

```bash
sudo ip link set can0 up type can bitrate 250000
```

For a virtual bus on a single host (useful for testing without a HAT):

```bash
sudo modprobe vcan
sudo ip link add dev can0 type vcan
sudo ip link set up can0
```

### 3. (Optional) Retrain the model

The repo ships with `model.joblib`, but you can retrain from `data.csv`:

```bash
jupyter nbconvert --to notebook --execute train_model.ipynb --inplace
```

The retraining run is itself an AIBOM-relevant event: the dataset hash, library versions, hyperparameters, and resulting model hash are all metadata the framework would capture.

### 4. Run the inference loop

```bash
python run_detector.py
```

You should see `Listening on CAN...` and then per-frame `OK` / `ANOMALY` lines.

### 5. Inject test frames

From another terminal (or another node), use `can-utils`:

```bash
# Normal Address Claim — well-formed NAME
cansend can0 18EEFF00#001A4F0100000000

# Anomalous Address Claim — NULL NAME
cansend can0 18EEFF00#0000000000000000
```

Expected output from the detector:

```
OK: 18EEFF00
ANOMALY detected: 18EEFF00#0000000000000000
```

`cansend` here plays the role of a *write tool* in the paper's tools lane — a real-world side effect on the bus.

## The AIBOM artifacts in this repo

The `aibom/` directory contains a worked example of the framework's output for this demonstrator:

- **`interfaces.yaml`** — formal contract for each metadata Interface in the system IBD. Each IF is the metadata-port of one block (Data, Training, Registry, Inference, Tool) and lists the required, optional, and conditional properties that block must expose. This is the schema; the graph is the instance.
- **`aibom.ttl`** — the knowledge graph for this demonstrator in Turtle/RDF. Every fact carries an `aibom:exposedVia` triple linking it back to the IF that surfaces it, so a SPARQL query like *"show me everything Data IF exposes"* is one line. Provenance is modelled with W3C PROV-O (`prov:Activity`, `prov:wasGeneratedBy`, `prov:wasInformedBy`).
- **`aibom.cdx.json`** — the same graph rendered as a CycloneDX 1.6 ML-BOM, with `data`, `application`, `machine-learning-model`, and `library` components, a `modelCard` block, and `dependencies`/`compositions` edges. This is the artifact a downstream supply-chain tool would ingest.

The Turtle graph is the source of truth: hashes, library versions, training environment, sampling strategy, cleaning transforms, partition, model lineage, inference contract, and tool side-effect classification all live there. The CycloneDX file is a projection of that graph into the standards-aligned format. If you regenerate `model.joblib`, both files need to be regenerated against the new hash.

The graph also illustrates honest provenance: the labelled dataset was **synthesized via ChatGPT** rather than collected from a real bus, and that fact is recorded as a `prov:SoftwareAgent` linked to the `DataCollection` activity. The framework treats synthetic-LLM-generated data as a first-class provenance class, not a footnote.

## Why this is a useful AIBOM test case

- **All five lanes are exercised** — most ML demos collapse the registry and tool lanes; running this on a real bus forces both to be modelled.
- **Cyber-physical side effects are visible** — write-tool invocations (CAN transmits) are a first-class node type in the graph, not a footnote.
- **The dataset is small enough to inspect by hand** — six labelled rows means readers can verify the dataset → model → prediction provenance chain manually before scaling up.
- **The threat surface is concrete** — the paper's evasion and poisoning threat model can be illustrated against this same pipeline (e.g., a poisoned `data.csv` row, or an evasion frame that flips `is_zero_name`'s decision).

## Limitations

This repository is a *minimum viable AI application* for the AIBOM workflow. It is not a production J1939 IDS:

- The training set is illustrative (a handful of rows).
- Only one PGN (`18EEFF00`) and one anomaly class (NULL NAME) are covered.
- The `timestamp` feature is fixed at inference, so the model effectively decides on `source_address` and `is_zero_name` alone.
- No frame validation, rate-limiting, or downstream alerting is implemented.

Reading the AIBOM produced from this pipeline should make all of the above directly visible — that is the point.

## Citation

If you use this demonstrator in academic work, please cite the paper above. A BibTeX entry will be added here once the proceedings are finalised.
