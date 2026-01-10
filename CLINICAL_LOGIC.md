# 🩺 Clinical Logic & Validation Specification

This document outlines the clinical assumptions, mathematical models, and prioritization heuristics used in the **Cardiac Service Strategy Lab**.

---

## 1. Dual-Pathway Risk Model
The simulation recognizes two distinct cohorts of patients, reflecting real-world cardiac waitlist dynamics.

### Pathway A: The Legacy Clock (10% Default)
This cohort represents high-risk patients who have already exceeded the 26-week threshold or are part of a high-complexity subgroup. 
* **The Rule:** If a Legacy patient hits Week 26, they automatically escalate to **Category 1**.
* **Rationale:** Mimics the "Breach Point" where clinical risk is deemed too high to wait any longer, mandating immediate intervention.

### Pathway B: The Standard Matrix (Stochastic Decline)
The remaining 90% of arrivals follow a probability-based decline using the **Poisson Distribution**.
* **The Logic:** Every week, the system calculates a $system\_lambda$ (the sum of individual deterioration probabilities).
* **Rationale:** This creates "Deterioration Clusters"—weeks where multiple patients "crash" simultaneously, testing ward resilience.



---

## 2. Resource Consumption & The Gamma Distribution
Length of Stay (LOS) is not fixed; it is modeled using a **Gamma Distribution** to account for clinical outliers.

| Category | Clinical Urgency | Mean LOS | Mathematical Distribution |
| :--- | :--- | :--- | :--- |
| **Cat 1** | Critical / Emergent | 22 Days | $Gamma(k=22, \theta=Slider)$ |
| **Cat 2** | Urgent | 11 Days | $Gamma(k=11, \theta=Slider)$ |
| **Cat 3** | Semi-Urgent | 5 Days | $Gamma(k=5, \theta=Slider)$ |
| **Cat 4** | Routine | 2 Days | $Gamma(k=2, \theta=Slider)$ |



**The "Bed-Blocker" Effect:** By using a Gamma tail rather than a simple average, the model creates realistic "Crisis Weeks" where a single patient might stay 40 days instead of 22, causing a "Bed-Choke" for new admissions.

---

## 3. Prioritization & MDT Logic
The admission engine mimics the multidisciplinary team (MDT) decision-making process:
1.  **Clinical Category:** Cat 1 (High Acuity) always moves to the front of the queue.
2.  **Wait Time:** Within categories, the longest-waiting patient is prioritized.

**Sorting Logic:** `idx = np.lexsort((-backlog[:, 1], backlog[:, 0]))` 
*(Sorts by Weeks Waiting descending, then Category ascending)*

---

## 4. Operational "Bed-Choke" Logic
A surgery is logged as a **"Cancellation"** when theater slots are available but effective bed capacity is zero.

* **Effective Capacity:** $Total\ Beds - Safety\ Buffer$
* **The Buffer:** Represents beds reserved for emergency non-elective admissions (e.g., emergency department arrivals). Without this, the model assumes 100% efficiency, which is clinically unsafe.

---

## 5. Metrics & Stability Scoring
The **Stability Score (%)** evaluates the health of the configuration:
* **Throughput:** Success in reducing the 26-week legacy count.
* **Efficiency:** Penalization for every "Bed-Choke" cancellation.

A high stability score indicates a **"Balanced System"** where theater throughput is perfectly matched to ward discharge rates.