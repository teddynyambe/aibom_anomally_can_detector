# AIBOM Anomaly CAN Detector

A reference demonstrator that accompanies the paper *"A Graph-Based Metadata Model for AI Bills of Materials in Cyber-Physical Systems"*. The paper proposes a Model-Based Systems Engineering (MBSE) approach to unifying AI-related artifacts — datasets, models, pipelines, configurations, runtime components, and provenance — inside a single knowledge graph that serves as the source of truth for generating AIBOMs aligned with SPDX and CycloneDX AI extensions.

This repository contains the concrete AI application referenced at the end of the abstract: a small machine-learning anomaly detector deployed over an automotive CAN bus. It is intentionally minimal so readers can reproduce the demo end-to-end and inspect the artifacts an AIBOM generator would index. The framework, knowledge-graph schema, and AIBOM generation pipeline are described in the paper itself; this repo is the *target system*, not the framework.

---

## What the detector does

The detector watches a J1939 CAN bus and flags anomalous **Address Claim** messages.

In SAE J1939, every Electronic Control Unit (ECU) broadcasts an *Address Claim* (PGN `0x00EEFF`, full ID `18EEFF00`) on power-up to claim a source address. The 8-byte payload carries the ECU's 64-bit **NAME** — a unique identifier composed of manufacturer code, identity number, function, and other fields. A NAME of all zeros is invalid by the standard and is symptomatic of:

- a malformed / spoofed address-claim frame,
- a misbehaving or compromised ECU,
- a basic denial-of-address-claim attack.

The classifier in this repo learns to distinguish well-formed Address Claims from the all-zero-NAME pathological case using a tiny labelled dataset.

---

## Repository layout

| Path | Purpose |
| --- | --- |
| `data.csv` | Labelled training samples — `timestamp, can_id, data, label`. |
| `train_model.ipynb` | Feature extraction + `RandomForestClassifier` training; emits `model.joblib`. |
| `model.joblib` | Pre-trained model committed for convenience. |
| `run_detector.py` | Loads `model.joblib`, opens `socketcan` on `can0`, predicts per frame. |
| `requirements.txt` | Python runtime dependencies. |

### Feature vector

Both training and inference use the same three features, in this order:

1. `source_address` — low byte of the 29-bit CAN ID (J1939 SA field).
2. `is_zero_name` — `1` if the 8-byte payload is `0000000000000000`, else `0`.
3. `timestamp` — inter-frame timing; trained from the CSV column, fixed to `0` at inference.

If you change the feature set, change it in **both** `train_model.ipynb` and `run_detector.py`.

---

## Reproducing the demo

### Hardware

- Raspberry Pi 3B+ or newer (any Linux host with SocketCAN works).
- A CAN HAT: PiCAN2, Waveshare RS485-CAN-HAT, or any MCP2515-based board.
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

### 4. Run the detector

```bash
python run_detector.py
```

You should see `Listening on CAN...` and then per-frame `OK` / `ANOMALY` lines as traffic arrives.

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

---

## How this maps to the AIBOM

The paper's contribution is the metadata model and the knowledge graph — not the classifier. When the framework is pointed at this repository, each of the following becomes a node in the graph, with provenance edges between them:

- **Dataset node** — `data.csv` (rows, label distribution, content hash, source).
- **Pipeline node** — `train_model.ipynb` (feature-extraction logic, hyperparameters, library versions).
- **Model node** — `model.joblib` (algorithm, training-data lineage, training-environment fingerprint).
- **Runtime node** — `run_detector.py` (deployment target, bus configuration, feature-vector contract).
- **Platform node** — the Raspberry Pi + CAN HAT (hardware identifiers, kernel/SocketCAN versions).

The graph is then rendered as an SPDX 3.0 AI profile or CycloneDX ML-BOM. Refer to the paper for the schema, traversal rules, and threat-modelling reasoning that the graph supports.

---

## Limitations of the demonstrator

This is a deliberately small demo. It is not a production J1939 IDS:

- The training set is illustrative (a handful of rows) — not statistically meaningful.
- Only one PGN (`18EEFF00`) and one anomaly class (NULL NAME) are covered.
- The `timestamp` feature is fixed at inference, so the model effectively decides on `source_address` and `is_zero_name` alone.
- No frame validation, rate-limiting, or downstream alerting is implemented.

The point is to give the AIBOM tooling something concrete and reproducible to index, not to ship a detector.

---

## Citation

If you use this demonstrator in academic work, please cite the accompanying paper. A BibTeX entry will be added here once the proceedings are finalised.
