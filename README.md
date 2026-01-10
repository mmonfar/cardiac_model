<<<<<<< HEAD
# 🏥 Cardiac Service Strategy Lab (v2.0)

An AI-powered decision support tool designed to resolve the disconnect between **Theater Planning** and **Bed Management**. 

=======
>>>>>>> 90270b11f04eca2e659494c75dc264690f25e4b9
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
<<<<<<< HEAD
   pip install -r requirements.txt
=======
   pip install -r requirements.txt
Launch the dashboard:Bashstreamlit run app.py
📊 Dashboard ModulesTabPurposeStrategic DashboardSide-by-side comparison of Baseline, Proposed, and AI-Optimized scenarios. Focuses on long-term waitlist trends and "Annual Choke" metrics.Operations ManagerA granular, short-term tool. Input the current status of every bed in the ward to generate a 7-day "Prescription" for admissions.📝 Assumptions & LogicNursing Ratios: Staffing is calculated at 4.5 FTE per bed to maintain 24/7 safe coverage.Priority Logic: Admissions are prioritized by Clinical Category (1-5) first, then by Waitlist Age (longest waiters).Bed Buffers: Scenarios can be tested with "Safety Buffers" (beds held empty for emergency arrivals) to see the impact on elective throughput.📂 Project Structureapp.py: The user interface, sidebar management, and session state.engine.py: The simulation logic, patient aging, and AI solver.visuals.py: Custom Plotly charts, CSS-styled ward maps, and metric cards.


---

### Additional Files

To complete your setup, here are the other two small files:

**`requirements.txt`**
```text
streamlit
pandas
numpy
plotly
.gitignorePlaintextvenv/
__pycache__/
.streamlit/
*.pyc
.DS_Store
>>>>>>> 90270b11f04eca2e659494c75dc264690f25e4b9
