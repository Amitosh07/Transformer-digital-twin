# Transformer Digital Twin — Web Presentation Layer

> **AI-powered Digital Twin of a Distribution Transformer for Condition Monitoring and Predictive Maintenance**  
> Built for the CPRI / PowerNext Smart Grid Innovation Track.  
> Governed by **Canonical Data Schema v1.0.0** (`dataschema.md`) and **ML Contract v1.0.0** (`mlcontract.md`).

---

## ⚡ Overview

This web application represents the presentation and live demonstration layer of the **Transformer Digital Twin**. It transforms complex electrical, thermal, and mechanical SCADA telemetry into an intuitive, high-conviction decision-support system for utility control rooms, substation engineers, and hackathon judges.

### Key Differentiators for Judges
1. **Physics-Informed Thermal Residual ($\Delta T = T_{\text{obs}} - T_{\text{model}}$):** Implements the IEEE C57.91 differential thermal equation to isolate cooling degradation and hot spots **48 hours before conventional trip alarms fire**.
2. **60 FPS Real-Time 3-Phase Vector Canvas:** Interactive HTML5 canvas rendering Phases L1, L2, L3 and resulting zero-sequence neutral current waveforms with live vector asymmetry detection.
3. **6-Pillar Composite Health Index (0–100):** Transparent, explainable asset rating weighted across Thermal (25%), Electrical (20%), Loading (15%), Oil Condition (15%), Protection (15%), and Anomaly (10%).
4. **Interactive Fault Injection Studio:** Test Overload (138%), Cooling Loss (Rapid $\Delta T$ rise), Phase Imbalance, and Conservator Oil Leakage deterministically.
5. **Contract Purity:** Complete decoupling from raw vendor schemas. Strictly rejects unverified line voltages (`VL12, VL23, VL31`) and prohibits silent zero-filling.

---

## 🛠️ Technology Stack

- **Framework:** React 19 + Vite 8 + TypeScript
- **Styling:** Tailwind CSS v4 (Matte obsidian cyber-physical SCADA aesthetic)
- **Vector Graphics:** HTML5 Canvas API (60fps requestAnimationFrame)
- **Icons:** Lucide React + custom SVG marks
- **Visual Micro-animations:** CSS keyframe pulses, SVG glow filters, canvas-confetti

---

## 📂 Project Structure

```
frontend/
├── public/
│   └── assets/
│       ├── transformer_hero.jpg       # Holographic CAD cutaway of transformer
│       └── transformer_schematic.jpg  # Engineering CAD schematic & blueprint
├── src/
│   ├── components/
│   │   ├── Navbar.tsx                 # Status HUD, schema pill, theme toggle
│   │   ├── Hero.tsx                   # Editorial headline, CAD cutaway, telemetry ticker
│   │   ├── Problem.tsx                # Why static thresholds & black-box ML fail
│   │   ├── Solution.tsx               # Physics ODE + ML residual explanation
│   │   ├── InteractiveTwinStudio.tsx  # Signature interactive demo & sandbox
│   │   ├── ThreePhaseWaveformCanvas.tsx# 60fps AC vector canvas
│   │   ├── ThermalResidualChart.tsx   # Dual thermal curves (Observed vs Model)
│   │   ├── HealthIndexDial.tsx        # 6-pillar radial gauge dial
│   │   ├── PrescriptiveActionCard.tsx # Operator work orders & JSON contract
│   │   ├── PipelineWalkthrough.tsx    # 6-stage canonical pipeline stepper
│   │   ├── FeaturesGrid.tsx           # Technical capability matrix
│   │   ├── ImpactMetrics.tsx          # Quantified utility gains (+48h, -74%)
│   │   ├── Architecture.tsx           # Topology, CAD blueprint, schema tree, FastAPI
│   │   ├── Team.tsx                   # 4 ownership pillars from dataschema.md
│   │   ├── Roadmap.tsx                # Baseline to CPRI testbed milestones
│   │   ├── PitchDeckCTA.tsx           # One-command Docker startup snippet
│   │   ├── GithubIcon.tsx             # Clean SVG GitHub mark
│   │   └── Footer.tsx                 # Compliance metadata and attribution
│   ├── data/
│   │   ├── assets.ts                  # Substation transformer nameplates & scenarios
│   │   └── scadaSimulation.ts         # IEEE thermal rise model & health calculation
│   ├── types.ts                       # Canonical Schema v1.0.0 TypeScript types
│   ├── App.tsx                        # Master application layout & theme manager
│   ├── main.tsx                       # React DOM root entry
│   └── index.css                      # Tailwind v4, custom scrollbars, cyber grid
├── package.json
└── vite.config.ts
```

---

## 🚀 Running Locally

### 1. Prerequisites
- Node.js 18+ (tested on Node v24)
- npm or yarn

### 2. Installation
```bash
cd frontend
npm install
```

### 3. Start Development Server
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### 4. Build for Production
```bash
npm run build
```

### 5. Preview Production Build
```bash
npm run preview -- --port 4173 --host
```
Open [http://localhost:4173](http://localhost:4173) in your browser.

---

## 🐳 Docker Deployment

To launch the frontend alongside the FastAPI backend, PostgreSQL database, and SCADA simulator:

```bash
# In the root repository directory
docker compose up --build
```

---

## 🎯 Judging Walkthrough (5-Minute Winning Pitch)

1. **First 15 Seconds (Hero):** Point out the live telemetry stream ticker ($I_{L1}, I_{L2}, I_{L3}, OTI, WTI$) and the holographic CAD cutaway showing the physical sensor layout.
2. **Minute 1 (The Problem vs Solution):** Contrast standard threshold alarms (which sleep during winter overloads) against our **Thermodynamic Residual ($\Delta T = T_{\text{obs}} - T_{\text{model}}$)**. Show the IEEE differential thermal equation.
3. **Minute 2–3 (The Live Interactive Demo):**
   - Click **"Severe Grid Overload (138%)"**: Watch the loading surge to 138%, temperature climb, and WATCH priority issue.
   - Click **"Cooling Radiator Failure"**: Point out how $T_{\text{observed}}$ surges $+18.6^{\circ}\text{C}$ above $T_{\text{model}}$, the **Thermal Residual** goes crimson, the Health Index drops to 42, and an **URGENT** work order is generated with reason code `#RAPID_TEMP_RISE`.
   - Click **"Phase Asymmetry & Neutral Surge"**: Watch the 60fps canvas waveform skew, revealing the surging zero-sequence neutral current wave!
   - Click **"Nominal Baseline"**: Trigger the green recovery with confetti.
4. **Minute 4 (Architecture & Contracts):** Open the **Canonical Schema** tab under Architecture to show how `dataschema.md` strictly insulates the project from messy Kaggle/CPRI column differences.
5. **Minute 5 (Team & Roadmap):** Highlight the 4 distinct ownership pillars and one-command Docker deployment.
