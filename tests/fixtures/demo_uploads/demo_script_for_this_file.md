# 🛡️ RippleGuard Video Recording Demo Script

> **Target Manifest:** `tests/fixtures/demo_uploads/video_demo_package_lock.json`  
> **Source Project:** `ecommerce-order-service` (v2.4.0) — Real Production Node.js Microservice  
> **Scale:** **164 Packages** • **267 Dependency Edges** (dwarfs the 64-node demo by 2.6x)  
> **Total Ingestion & Analysis Latency:** **~35 ms** (< 0.1s end-to-end, zero UI lag)

---

## Quick Reference: Key Narrative Points & Exact Metrics

| Narrative Point | Target Package(s) | Exact Value / Finding to Call Out |
| :--- | :--- | :--- |
| **1. Hidden Critical Package** | `es-errors`<br/>*(Alternative: `safe-buffer`)* | **CVSS 1.0** (benign/no CVEs), but **In-Degree 9**, **Transitive 17**.<br/>Composite Score: **68.5 (HIGH Tier)** • Flagged **Hidden Critical: True**.<br/>*(Alternative: `safe-buffer` has CVSS 1.0, InDeg 9, Transitive 16, Score **66.1**)* |
| **2. Betweenness Bridge** | `get-intrinsic` | In-Degree is only **4**, but Betweenness Centrality is **0.00350** (11x higher than `debug`).<br/>When Betweenness weight is set to 25%, rank jumps from #8 to **#2** (Score: **54.8**, BW Subscore: **100.0**). |
| **3. Overlapping Blast Radii** | `debug` + `es-errors` | `debug` alone: **13 pkgs** • `es-errors` alone: **18 pkgs**.<br/>Combined multi-origin: **27 pkgs** • Shared overlap: **4 pkgs** (`axios`, `body-parser`, `express`, `ecommerce-order-service`). |
| **4. Monte Carlo Reality Gap** | `ms`<br/>*(Alternative: `debug`)* | BFS claims **18 pkgs (100%)** affected.<br/>Monte Carlo (1,000 trials) proves expected affected is only **8.5 pkgs** (47.3% mean prob).<br/>`compression` (16.4%) and `axios` (17.0%) are insulated due to pinned dependencies. |
| **5. Fix This First Consolidation**| `es-errors`, `safe-buffer`, `ms`, `function-bind` | Headline: *"Fixing these 4 packages addresses 100% of all currently flagged risk across 5 alerts."*<br/>Fixing just #1 and #2 eliminates **75.0%** of cumulative risk. |

---

## Step-by-Step Recording Walkthrough

### Scene 1: Cold Start Landing Page & Instant Upload (0:00 – 0:30)
1. **Starting State:** Screen shows the RippleGuard Landing Page at `http://localhost:8501`.
2. **Narration:**
   > *"Welcome to RippleGuard. Rather than locking users into static demo data, RippleGuard lets security teams and developers analyze their own real-world software supply chains entirely offline."*
3. **Action:**
   - Point to the two cards: **Card 1: 📂 Upload Your Own Project** and **Card 2: 🛡️ Try the Demo Dataset**.
   - Drag and drop (or browse to) `tests/fixtures/demo_uploads/video_demo_package_lock.json` into Card 1.
4. **Visual Payoff:**
   - App transitions to the dashboard in **35 milliseconds**.
   - Point to the top KPI metrics: **164 Packages**, **267 Edges**, and the banner badge showing `Uploaded: video_demo_package_lock.json`.
   - Contrast with the built-in 64-node demo: *"This is a full production e-commerce microservice — 164 packages resolved across a 6-deep dependency tree."*

---

### Scene 2: Unmasking the 'Hidden Critical' Package (0:30 – 1:15)
1. **Action:**
   - Click the package dropdown or locate `es-errors` in the **Risk Leaderboard**.
   - Select `es-errors`.
2. **Visual Payoff:**
   - Open the **Package Risk Dossier**.
   - Point out the **Hidden Critical** badge.
3. **Narration:**
   > *"Traditional vulnerability scanners look only at CVE databases. A standard SCA scanner assigns `es-errors` a CVSS score of 1.0 — completely benign, zero reported vulnerabilities. In most security dashboards, this package is invisible.*
   >
   > *RippleGuard tells a completely different story. Because 9 direct packages and 17 transitive consumers depend on `es-errors` throughout our HTTP request stack, its structural subscore drives its composite criticality to **68.5 — HIGH RISK**.*
   >
   > *A malicious compromise or unannounced breaking update here threatens over 10% of our entire service topology."*

---

### Scene 3: Unveiling Hidden Bridges with Betweenness Centrality (1:15 – 1:55)
1. **Action:**
   - Expand **⚙️ Weighting Tuning** in the sidebar.
   - Show the default weights: CVSS 35%, Transitive 35%, In-Degree 30%, Betweenness 0%.
   - In the leaderboard, show that `get-intrinsic` is ranked **#8** with In-Degree 4.
2. **Action:**
   - Move the **Betweenness Centrality Weight** slider to **25%**.
3. **Visual Payoff:**
   - Watch the leaderboard re-order live.
   - `get-intrinsic` leaps from Rank 8 to **Rank #2** with a score of **54.8** and a normalized Betweenness score of **100.0**.
4. **Narration:**
   > *"In-degree alone only finds popular utilities. But what about structural bottlenecks — packages that act as mandatory bridges across dependency paths?*
   >
   > *Notice `get-intrinsic`. Its direct in-degree is only 4, but its betweenness centrality is **0.00350** — over 11 times higher than the most popular package in the project (`debug`). By dialing in Betweenness centrality, RippleGuard instantly surfaces this critical architectural choke point."*

---

### Scene 4: Multi-Origin Cascading Blast Radius Simulation (1:55 – 2:35)
1. **Action:**
   - Reset weights (or leave Betweenness) and select `debug`.
   - Click **"Simulate Compromise"**.
   - Show the red blast propagation tree: **13 packages affected** (reaching `express`, `body-parser`, `axios`).
2. **Action:**
   - Under Multi-Compromise, add `es-errors` as a second origin node.
   - Click **"Simulate Multi-Compromise"**.
3. **Visual Payoff:**
   - Blast Radius card expands to **27 packages**.
   - Look at the Attack Tree and Multi-Origin overlap indicator.
4. **Narration:**
   > *"Modern supply chain attackers rarely compromise only one package. Let's simulate a simultaneous compromise of both `debug` and `es-errors`.*
   >
   > *Individually, `debug` affects 13 packages and `es-errors` affects 18. Together, they cascade across **27 packages**, intersecting directly at 4 critical application choke points: `axios`, `body-parser`, `express`, and our root service. RippleGuard pinpoints exactly where multi-vector compromises converge."*

---

### Scene 5: Deterministic BFS vs. Monte Carlo Probabilistic Reality (2:35 – 3:15)
1. **Action:**
   - Select `ms` in the package selector.
   - Show the deterministic BFS blast alert: **18 packages affected (100% reach)**.
2. **Action:**
   - Toggle the simulation mode from **"Deterministic (BFS)"** to **"Monte Carlo (Probabilistic)"**.
   - Keep 1,000 trials selected.
3. **Visual Payoff:**
   - Monte Carlo runs in **11 milliseconds**.
   - The Expected Blast Radius card renders: **8.5 packages** (Mean probability: **47.3%**).
   - Point to the partial propagation breakdown: deep consumers like `compression` (16.4%) and `axios` (17.0%) drop to under 20% infection probability.
4. **Narration:**
   > *"Deterministic BFS assumes a worst-case scenario: that 100% of malicious versions propagate infinitely across every edge. In reality, modern lockfiles enforce exact version pins and semantic version bounds.*
   >
   > *When we toggle RippleGuard's Monte Carlo engine, 1,000 stochastic trials execute in just 11 milliseconds. The expected blast radius plummets from 18 packages down to 8.5. Upstream services like `compression` and `axios` have less than a 17% chance of receiving the payload due to pinned intermediary dependencies.*
   >
   > *This distinction saves engineering teams dozens of hours of false-alarm triage."*

---

### Scene 6: "Fix This First" Consolidated Remediation (3:15 – 3:45)
1. **Action:**
   - Use the sticky navigation bar: click **🎯 Fix This First**.
   - Page smoothly scrolls to the Fix This First section.
2. **Visual Payoff:**
   - Point out the headline banner:
     > *"Fixing these 4 packages addresses 100% of all currently flagged risk across 5 alerts."*
   - Review Fix #1 (`es-errors`, Low effort) and Fix #2 (`safe-buffer`, Low effort).
3. **Narration:**
   > *"Finally, RippleGuard eliminates alert fatigue. Instead of forcing developers to address dozens of disconnected security tickets, our set-cover greedy algorithm consolidates remediation.*
   >
   > *By executing just the top two low-effort recommendations — pinning `es-errors` and `safe-buffer` to verified digests — developers eliminate **75% of the cumulative blast radius** across the entire 164-package project.*
   >
   > *Actionable, explainable, and zero alert fatigue."*
