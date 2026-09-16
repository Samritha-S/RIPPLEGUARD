# RippleGuard — Demo Day Presentation Cheatsheet

> **Hackathon Track:** UN SDG 9 (Industry, Innovation & Infrastructure)  
> **Mission:** Transform opaque software supply chains into transparent, explainable, and resilient digital infrastructure.

---

## ⚠️ Disclosure Reminder (If a Judge Asks)
> **Data Transparency:**
> 1. **Graph Topology & Structural Metrics:** 100% computed directly from the resolved dependency graph (in-degree, transitive reachability, betweenness centrality, shortest paths).
> 2. **Vulnerability Data:** Supported via live queries to the **OSV.dev API** (toggle in sidebar). In offline demonstration mode, representative curated supply-chain profiles (e.g. `debug=5.3`, `mime-types=2.5`) or a standard benign baseline (`1.0`) are used for zero-latency presentation reliability.
> 3. **Monte Carlo Probabilities & Effort Tiers:** Disclosed heuristic estimates derived from manifest version constraints (e.g. pinned vs floating ranges) and action taxonomies (Low to Very High), not measured engineering labor data.

---

## 📊 Exact Scenario Metrics Reference Table

| Metric | Scenario 1: `debug` (Primary) | Scenario 2: `mime-types` (Secondary) | Scenario 3: `debug` + `mime-types` (Multi-Origin) |
| :--- | :--- | :--- | :--- |
| **Base CVSS** | **5.3 / 10** *(Curated CVE)* | **2.5 / 10** *(Curated CVE)* | *Multi-origin union* |
| **Composite Score** | **79.5 / 100** | **58.6 / 100** | - |
| **Risk Tier** | **CRITICAL RISK** (Coral Red) | **HIGH RISK** (Amber Orange) | - |
| **Direct Dependents (In-Deg)** | **7** direct packages | **5** direct packages | - |
| **Transitive Blast Radius** | **9** packages (10 total affected) | **8** packages (9 total affected) | **14 total affected** (5 multi-origin overlap) |
| **Affected Application Seeds** | **3 seeds:** `axios`, `express`, `morgan` | **2 seeds:** `axios`, `express` | **3 seeds:** `axios`, `express`, `morgan` |
| **Maximum Propagation Hops** | **2 hops** | **2 hops** | **2 hops** |
| **Monte Carlo Finding (FR-4.4)** | `send` (97.2%), `body-parser` (95.7%) | `form-data` (85.9%), `accepts` (64.3%) | **`morgan` drops to ~19.6%** likelihood! |

---

## 🎬 Live Demo Script & Click Sequences

### Cold Open: The Elevator Pitch (30 seconds)
1. **Open the browser** to `http://localhost:8501`.
2. **Point to the Header & KPI Cards:**
   - *"Software supply chains are the hidden foundation of SDG 9 digital infrastructure. Standard security tools report isolated CVE scores, but completely miss blast radius—how far a compromised package ripples downstream."*
   - Point out: **64 Analyzed Packages**, **100 Dependency Links**, **5 Seed Applications**.

---

### Scenario 1: `debug` (Foundational Utility Amplification)
*Story: How a modest 5.3 CVE in a logging utility turns into a systemic CRITICAL threat.*

1. **Observe Initial State:**
   - Notice that **`debug`** is already pre-selected upon launch.
   - Point out the **Package Risk Dossier**:
     - *"Notice the base CVSS is only **5.3/10**—many security teams would triage this as medium priority."*
     - *"However, RippleGuard flags it as **CRITICAL RISK (79.5/100)** because it directly touches 7 packages and transitively ripples into 9 packages."*
   - Read the generated explanation:
     > *"debug is flagged as CRITICAL RISK due to structural amplification... exposing 3 top-level application seeds: axios, express, morgan."*
2. **Click Button:** Click **`🚨 Simulate`** (in the sidebar).
3. **Point to the Graph & Alert:**
   - **Graph Highlight:** Point out `debug` glowing in red/magenta, with downstream affected packages and attack paths illuminated in **vibrant lavender**.
   - **Attack Propagation Tree:**
     - Point out the 1-hop reach to server frameworks: `debug ➔ express` and `debug ➔ morgan`.
     - Point out the 2-hop reach to client HTTP stacks: `debug ➔ https-proxy-agent ➔ axios`.
4. **Click Button:** Click **`↺ Reset`** to clear the simulation.

---

### Scenario 2: `mime-types` (Cross-Ecosystem Supply Chain Entanglement)
*Story: How a file-type lookup table bridges server-side Express and client-side Axios.*

1. **Select Package:** In the sidebar dropdown, select **`mime-types`**.
2. **Point to the Package Risk Dossier:**
   - *"Here is `mime-types`—a simple MIME lookup utility with an innocuous base CVSS of **2.5/10**."*
   - *"Yet RippleGuard rates it **HIGH RISK (58.6/100)** because it bridges two completely distinct software ecosystems."*
3. **Click Button:** Click **`🚨 Simulate`**.
4. **Point to the Graph & Attack Tree:**
   - Server path (1 hop): `mime-types ➔ express`
   - Client path (2 hops): `mime-types ➔ form-data ➔ axios`
   - *"A single poisoned package in `mime-types` silently compromises both your incoming HTTP request parser in Express and your outgoing HTTP multipart client in Axios."*
5. **Click Button:** Click **`↺ Reset`**.

---

### Scenario 3: Multi-Origin Blast Overlap & Monte Carlo Probability (FR-4.3 / FR-4.4)
*Story: Why worst-case BFS is only half the story, and how pin constraints protect downstream systems.*

1. **Multi-Select Origins:** In the sidebar multi-select, choose both **`debug`** and **`mime-types`**.
2. **Click Button:** Click **`🚨 Simulate`**.
3. **Point out the Golden Amber Triangles (FR-4.3):**
   - 5 packages (`axios`, `body-parser`, `express`, `send`, `serve-static`) are reachable from both origins simultaneously.
   - Total blast radius is the topological union of 14 packages ($10 + 9 - 5 = 14$).
4. **Switch to Monte Carlo Mode (FR-4.4):**
   - Toggle **Propagation Mode** to **"Monte Carlo (probability-weighted)"**.
   - Click **`🚨 Simulate`** (executes 1,000 trials in ~12 ms).
5. **THE KEY DEMO BEAT — `morgan`:**
   - *"Deterministic BFS claims all 14 packages are infected with 100% certainty."*
   - *"Look at the Monte Carlo probability panel: **`morgan` drops all the way down to ~19.6% infection likelihood** ($\pm 0.0126$)."*
   - *"Why? Because `morgan` has strict version pin constraints across its incoming edges—it does not automatically ingest floating transitive updates!"*
   - This prevents unnecessary panic and gives security teams calibrated risk intelligence.

---

### Scenario 4: Fix Consolidation ("Fix This First") & 2D ROI Ranking (FR-5.2)
*Story: How to solve Dependabot-style alert fatigue by remediating overlapping blast radius.*

1. **Scroll to the `🎯 Fix This First` panel** (in the right column).
2. **Show Pure Coverage Ranking:**
   - Select **"Rank by coverage"**.
   - Point out the sequence: `#1 ms` (61.1%) $\to$ `#2 mime-types` (83.3%) $\to$ `#3 depd` (94.4%) $\to$ `#4 on-finished` (100.0%).
3. **Toggle to Efficiency Ranking (FR-5.2):**
   - Select **"Rank by efficiency (coverage per effort)"**.
   - *"Notice what happened: **`on-finished` (Low Effort • ROI 5.6) leapfrogged `depd` (High Effort • ROI 3.7) into Rank #3!**"*
   - *"Why? Replacing `depd` is a major breaking change requiring architectural rewrites. `on-finished` is an easy pin update that gives immediate security return for minimal engineering labor."*

---

### Scenario 5: Containment & Export
1. Select **`dotenv`** and click **`🚨 Simulate`**:
   - Point to the **Zero-Downstream Root Application** banner (proves the tool recognizes leaf containment).
2. Click **`📄 Export Report (Markdown)`**:
   - Downloads a complete audit report reflecting active simulation modes and dual remediation rankings.
