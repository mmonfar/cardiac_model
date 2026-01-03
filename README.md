I understand. I will provide the complete README.md content in a single, clean Markdown block so you can copy it entirely in one go.Markdown# 🏥 Cardiac Service Strategy Lab: Resolving the Bed-Day Paradox

## 🎯 The Problem This Solves
Many surgical services face a "Bed-Day Choke." When management increases surgical slots to clear a backlog, they often see an unexpected rise in **day-of-surgery cancellations**. This happens because the model lacks the post-operative bed capacity to absorb the increased throughput. 

This tool was developed to **resolve the disconnect between Theater Planning and Bed Management.** It uses a stochastic (randomized) simulation to prove that beds—not just theater time—are the primary lever for clearing 26-week clinical breaches.

---

## 🌟 Key Features

### 1. The AI Strategy Solver
The model doesn't just show data; it searches for a solution. The AI solver identifies the minimum combination of **Beds** and **Theater Slots** required to hit a "Zero Breach" state by a specific target week, ensuring that the legacy backlog is cleared sustainably.

### 2. Clinical Deterioration Engine
Unlike static spreadsheets, this model treats patients as living entities:
- **Risk Multiplier:** Patients waiting >26 weeks have a **2.0x higher risk** of clinical deterioration per week.
- **Dynamic Urgency:** A "Routine" Cat 4 patient can age into a "Critical" Cat 1 case, increasing their required Length of Stay (LOS) from 2 days to 22 days.

### 3. "Bed-Choke" Quantification
The tool tracks every time a surgery is "cancelled" in the simulation because the ward is at capacity. This provides a hard metric for **Operational Waste** and staff frustration caused by under-resourcing.

### 4. Live Ward Management
The "Operations Manager" allows users to input the current status of every bed (who is in it and how long they have left). This turns a strategic model into a tactical tool for Monday morning planning.

---

## 🚀 Getting Started

### 📦 Prerequisites
- Python 3.9 or higher
- [Recommended] A virtual environment (`python -m venv venv`)

### 🛠️ Installation
1. Install the required libraries:
   ```bash
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