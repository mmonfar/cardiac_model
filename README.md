# 🏥 Cardiac Service Strategy Lab (v2.0)

An AI-powered decision support tool designed to resolve the disconnect between **Theater Planning** and **Bed Management**.

---

## 🎯 The Problem This Solves

Many surgical services face a **“Bed-Day Choke.”** Increasing surgical slots to clear a backlog often leads to **day-of-surgery cancellations** because the ward cannot absorb the throughput.

This tool uses **stochastic simulation** to demonstrate that beds — not just theater time — are the primary lever for clearing **26-week clinical breaches**.

---

## 🌟 Key Features

### 1. The AI Strategy Solver

The model searches for the optimal solution using a **heuristic optimization engine**. It identifies the *minimum viable combination* of:

- **Beds**
- **Theater Slots**

required to achieve a **Zero Breach** state by a specified target week.

---

### 2. Dual-Pathway Clinical Engine

Unlike static spreadsheets, this model treats patients as **dynamic clinical entities**:

- **The 10% Legacy Clock**  
  10% of patients follow a “hard-breach” pathway, automatically escalating to **Category 1** at 26 weeks.

- **Stochastic Deterioration**  
  Remaining patients deteriorate according to a **Poisson-distributed probability matrix**.

- **Outlier Logic**  
  Length of Stay (LOS) is generated using a **Gamma Distribution**, reproducing real-world *bed-blocker* behavior.

---

### 3. “Bed-Choke” & Acuity Metrics

- Tracks **cancellations** caused by bed unavailability  
- Flags **High-Acuity Weeks** where patient mix requires **1:1 nursing ratios**

---

### 4. Live Ward Digital Twin

The **Operations Manager** allows users to input the live status of every bed, transforming a strategic model into a **tactical 7-day admission prescription tool**.

---

## 📊 Dashboard Modules

| Tab | Purpose |
| :--- | :--- |
| **Strategic Dashboard** | Side-by-side comparison of Baseline, Proposed, and AI-Optimized scenarios |
| **Operations Manager** | Bed-level inputs producing a 7-day admission “Prescription” |
| **Transparency Lab** | Visual validation of Poisson deterioration and Gamma LOS distributions |

---

## 🚀 Getting Started

```bash
# 1. Clone the repository
git clone https://github.com/your-username/cardiac-strategy-lab.git
cd cardiac-strategy-lab

# 2. Install requirements
pip install -r requirements.txt

# 3. Launch the dashboard
streamlit run app.py
```


## 📝 Assumptions & Logic

**Nursing Ratios**  
Staffing is calculated at 4.5 FTE per bed to maintain 24/7 safe coverage.

**Priority Logic**  
Admissions are prioritized by Clinical Category (1–5) first, then by waitlist age.

**Bed Buffers**  
Scenarios can be tested with safety buffers (beds held empty for emergency arrivals).

---

## 📂 Project Structure

app.py  
engine.py  
visuals.py

---

## 🛠️ Configuration Snippets

requirements.txt  
streamlit  
pandas  
numpy  
plotly  

.gitignore  
venv/  
__pycache__/  
.streamlit/  
*.pyc  
.DS_Store

## Licence

Code is licensed under **AGPL-3.0-or-later** (see [`LICENSE`](LICENSE)); a commercial licence is available on request from the author via [LinkedIn](https://www.linkedin.com/in/martin-monteagudo-farina/). Non-code content is under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Details in [`LICENSING.md`](LICENSING.md).

## Disclaimer

Research and demonstration software. Not a medical device and not intended for clinical decision-making, diagnosis or treatment. Provided "as is", without warranty of any kind; the author accepts no liability for any use. Uses synthetic data only.
