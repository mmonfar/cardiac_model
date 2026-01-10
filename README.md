# 🏥 Cardiac Service Strategy Lab (v2.0)

An AI-powered decision support tool designed to resolve the disconnect between **Theater Planning** and **Bed Management**. 

## 🎯 The Problem This Solves
Many surgical services face a "Bed-Day Choke." Increasing surgical slots to clear a backlog often leads to **day-of-surgery cancellations** because the ward cannot absorb the throughput. This tool uses stochastic simulation to prove that beds—not just theater time—are the primary lever for clearing 26-week clinical breaches.

---

## 🌟 Key Features

### 1. The AI Strategy Solver
The model searches for the optimal solution using a heuristic optimization engine. It identifies the minimum combination of **Beds** and **Theater Slots** required to hit a "Zero Breach" state by a specific target week.

### 2. Dual-Pathway Clinical Engine
Unlike static spreadsheets, this model treats patients as dynamic clinical entities:
- **The 10% Legacy Clock:** 10% of patients follow a "hard-breach" pathway, automatically escalating to Category 1 at 26 weeks.
- **Stochastic Deterioration:** The remaining patients decline based on a **Poisson-distributed** probability matrix.
- **Outlier Logic:** Length of Stay (LOS) is calculated using a **Gamma Distribution**, mimicking real-world "Bed-Blockers" who stay significantly longer than the average.



### 3. "Bed-Choke" & Acuity Metrics
The tool tracks "Cancellations" caused by bed shortages and flags **High Acuity Weeks** where the patient mix requires 1:1 nursing ratios.

### 4. Live Ward Digital Twin
The "Operations Manager" allows users to input the current status of every bed. It transforms a strategic model into a tactical tool for 7-day admission "prescriptions."

---

## 🚀 Getting Started

### 🛠️ Installation
1. Clone the repository and install requirements:
   ```bash
   pip install -r requirements.txt