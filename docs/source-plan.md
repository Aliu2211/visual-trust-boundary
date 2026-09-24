# Visual Trust Boundary: Testbed Implementation Plan

**Target device:** Raspberry Pi 5 (8 GB) + commodity USB webcam
**Goal:** one crafted machine readable code traced across three autonomy tiers, defense off and defense on, with metrics collected on the device itself.
**Scope note:** everything here runs in a controlled lab on hardware you own. All payloads are synthetic. No third party or in the wild system is touched.

---

## 1. Repository layout

Build the whole thing as one repo so it is releasable for reproducibility.

```
vtb-testbed/
  README.md
  requirements.txt
  config.yaml                # tiers, ports, model name, run settings
  decode/
    capture.py               # webcam or image folder -> decoded payloads
  tiers/
    tier1_rulebased.py       # access node (vulnerable + defended modes)
    tier2_analytics.py       # VMS-style parsing backend
    tier3_agent.py           # edge VLM agent wrapper
  defense/
    boundary.py              # the decode-time defense layer
    grammar.py               # allowlist schema/format rules
  attacks/
    generate.py              # payload families -> QR/barcode images
    payloads.yaml            # the attack set definition
  harness/
    run_experiments.py       # defense off then on, per family per tier
    metrics.py               # crossing rate, FPR, latency, memory
    results/                 # generated CSVs + plots
  ethics/
    LAB_ONLY.md              # controlled-lab statement, disclosure protocol
```

---

## 2. Device and OS setup

```bash
# Raspberry Pi OS (64-bit) Bookworm, headless is fine.
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-venv python3-pip libzbar0 zbar-tools \
                    libgl1 v4l-utils git
python3 -m venv ~/vtb && source ~/vtb/bin/activate
pip install --upgrade pip
pip install opencv-python-headless pyzbar qrcode[pil] python-barcode \
            fastapi uvicorn pydantic pyyaml psutil requests pandas matplotlib
```

`requirements.txt` pins exact versions once it runs, so the release is reproducible.

Confirm the camera and decoder before anything else:

```bash
v4l2-ctl --list-devices           # webcam present
python -c "from pyzbar.pyzbar import decode; print('zbar ok')"
```

---

## 3. Decode stage (the boundary lives here)

`decode/capture.py` has two input modes so results are reproducible:

- **Live:** grab frames from the webcam.
- **Replay:** read pre-generated code images from a folder (use this for the actual experiments, so decode-and-consume is isolated from capture noise).

It emits a payload record: `{payload, symbology, source_image, timestamp}`. This record is the thing that crosses the visual trust boundary. Everything downstream either trusts it (vulnerable) or routes it through `defense/boundary.py` first (defended).

```python
from pyzbar.pyzbar import decode
import cv2

def decode_image(path):
    img = cv2.imread(path)
    out = []
    for s in decode(img):
        out.append({"payload": s.data.decode("utf-8", "replace"),
                    "symbology": s.type, "source_image": path})
    return out
```

---

## 4. The three tiers

Each tier runs in one of two modes, chosen by config: `mode: vulnerable` or `mode: defended`. This single switch is what produces the defense-off vs defense-on comparison.

### Tier 1: rule-based access node
Represents a gate controller doing an identifier lookup. Use SQLite so injection is real but contained.

- **Vulnerable path:** the decoded payload is concatenated into a SQL string and into a shell command (deliberately, to demonstrate the crossing).
- **Defended path:** the payload goes through `defense.boundary.check()` first, then only parameterised queries and no shell.

```python
# vulnerable (demonstration only, lab)
cur.execute("SELECT * FROM badges WHERE id = '%s'" % payload)   # SQLi crosses here
# defended
pid = boundary.check(payload, use="identifier")                  # raises on bad input
cur.execute("SELECT * FROM badges WHERE id = ?", (pid,))         # payload is data
```

### Tier 2: analytics backend
A FastAPI service standing in for a video-management system that parses forwarded payloads. Exercises the server-side path and shows the widened surface (e.g. payload reaching a log parser or a secondary query).

### Tier 3: edge VLM agent
A small quantised VLM on the Pi CPU, wrapped so that "read the scene, decide an action" is a tool-calling loop.

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2-vl:2b        # or a MiniCPM-V build; pick the smallest that runs
```

- **Vulnerable path:** text read from the image is fed into the agent prompt as if it were an observation, so instruction-style payloads can hijack the tool call.
- **Defended path:** decoded/read content is wrapped with provenance separation so it cannot be promoted to instruction status, and any tool call passes the gate.
- **Record inference latency per image** here. That number is your edge-constraint finding, not a bug.

---

## 5. The defense layer

`defense/boundary.py` is the contribution. One entry point, three controls.

```python
def check(payload, use):
    validate(payload, use)          # 1. schema/format: length, charset, allowlist grammar
    return payload                  # caller then uses parameterisation/escaping (control 2)

def gate(action, context):          # 3. privilege minimisation + confirmation
    if action.is_consequential and not context.approved:
        raise Gated(action)
```

- **Control 1 (validate):** `grammar.py` holds an allowlist per use (`identifier`, `plate`, `ticket`). Reject on length bound, disallowed characters, or grammar miss.
- **Control 2 (escaping/parameterisation):** enforced at the call site in each tier (parameterised SQL, no shell string building, provenance tags for the agent).
- **Control 3 (gate):** consequential actions (open gate, agent tool call) require an explicit approval flag or policy pass.

Keep the layer tiny and measure its own cost; it must be cheap enough to sit on the Pi.

---

## 6. Attack set

`attacks/payloads.yaml` defines the families from the taxonomy; `generate.py` renders each to a QR or barcode PNG into a folder the replay decoder reads.

| Family | Example intent (synthetic) | Target tier |
|---|---|---|
| Malformed / oversized | very long string, control chars, truncated symbol | all (robustness) |
| Injection string | `' OR '1'='1`, `; $(...)`, `../../` style | Tier 1 |
| Backend parsing | payload shaped to trip the VMS parser / secondary query | Tier 2 |
| Instruction style | text that reads as a command to the agent | Tier 3 |

Generate a fixed, seeded set so runs are comparable.

```python
import qrcode
def make_qr(text, path):
    qrcode.make(text).save(path)
```

---

## 7. Experiment harness and metrics

`harness/run_experiments.py` loops: for each tier, for each family, run mode=vulnerable then mode=defended, N repetitions. `metrics.py` records to CSV.

Metrics captured:

- **Boundary crossing rate** per family per tier (did the payload reach and affect the trusted context?).
- **Detection / block rate** and **false positive rate** on a benign code set (defended mode).
- **Edge cost:** added latency per decode from the defense, plus tier-3 VLM inference latency, CPU and memory via `psutil`.
- **Usability:** benign workflow pass-through rate (benign codes must still work).

Output: tidy CSVs in `harness/results/`, then a small plotting script for the paper's figures. Fix random seeds and log versions (`pip freeze > requirements.txt`) for reproducibility.

---

## 8. Build order (maps to the proposal timeline)

1. Device + decode working (Section 2 to 3). Smallest end-to-end path first.
2. Tier 1 vulnerable, then defended. First real crossing + first block.
3. Attack generator + harness skeleton. Get one CSV out early.
4. Tier 2, then Tier 3 (VLM last, it is the slow part).
5. Defense layer hardened and cost-measured across all tiers.
6. Full runs, collect results, generate figures.
7. Fill Section 6 (Results) and finalise Discussion in both manuscripts.

**Guiding rule:** Tiers 1 to 2 give you a complete, submittable result on their own. Treat Tier 3 as the stretch that strengthens the paper, so a slow or partial VLM tier never blocks the thesis.

---

## 9. Ethics and disclosure (keep in the repo)

- Controlled lab only; hardware you own; synthetic payloads.
- Get institutional ethics sign-off before running.
- If a tested commercial device is found vulnerable: coordinated disclosure, private vendor notice, remediation window before publication, report via CERT/national channel.
- Release the defense and harness; keep attack detail limited to what validates the threat and the defense.
