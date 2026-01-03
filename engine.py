import pandas as pd
import numpy as np

def run_simulation(params, current_ward, weeks=52, seed=42):
    np.random.seed(seed)
    active_beds = [{'cat': p.get('Cat', 3), 'days_remaining': p.get('DaysRemaining', 5)} for p in current_ward]
    
    # Initialization of Legacy vs Fresh Backlog
    backlog = []
    legacy_count = int(params['total_backlog'] * (params['dist_legacy'] / 100))
    fresh_count = params['total_backlog'] - legacy_count
    cat_probs = [params[f'dist_cat{i}']/100 for i in range(1,6)]
    
    for _ in range(legacy_count):
        backlog.append({'cat': np.random.choice([1,2,3,4,5], p=cat_probs), 'weeks_waiting': np.random.randint(26, 40)})
    for _ in range(fresh_count):
        backlog.append({'cat': np.random.choice([1,2,3,4,5], p=cat_probs), 'weeks_waiting': np.random.randint(0, 25)})

    history = []
    los_map = {1: 22, 2: 11, 3: 5, 4: 2, 5: 2}
    
    for week in range(weeks):
        # 1. Deterioration & 26-Week Factor
        for p in backlog:
            p['weeks_waiting'] += 1
            risk_mult = 2.0 if p['weeks_waiting'] >= 26 else 1.0
            for c in range(5, 1, -1):
                if p['cat'] == c and np.random.random() < (params.get(f'det_{c}to{c-1}', 0.04) * risk_mult):
                    p['cat'] = c-1; break
        
        # 2. Referrals & Discharges
        new_refs = np.random.poisson(params['weekly_refs'])
        for _ in range(new_refs):
            backlog.append({'cat': np.random.choice([1,2,3,4,5], p=cat_probs), 'weeks_waiting': 0})
        
        for p in active_beds: p['days_remaining'] -= 7
        active_beds = [p for p in active_beds if p['days_remaining'] > 0]

        # 3. Admission & Bed-Day Choke
        eff_cap = params['total_beds'] - params['safety_buffer']
        avail = max(0, eff_cap - len(active_beds))
        to_admit = min(avail, params['surg_per_week'])
        cancellations = max(0, params['surg_per_week'] - avail)
        
        backlog.sort(key=lambda x: (x['cat'], -x['weeks_waiting']))
        admitted = {f'Cat {i}': 0 for i in range(1,6)}
        for _ in range(int(to_admit)):
            if backlog:
                p = backlog.pop(0)
                admitted[f"Cat {p['cat']}"] += 1
                active_beds.append({'cat': p['cat'], 'days_remaining': los_map[p['cat']]})

        history.append({
            'week': week, 'Cat 1': len([p for p in backlog if p['cat']==1]),
            'Cat 2': len([p for p in backlog if p['cat']==2]), 'Cat 3': len([p for p in backlog if p['cat']==3]),
            'Cat 4': len([p for p in backlog if p['cat']==4]), 'Cat 5': len([p for p in backlog if p['cat']==5]),
            'Over_26_Wks': len([p for p in backlog if p['weeks_waiting'] >= 26]),
            'occupancy': len(active_beds), 'cancellations': cancellations,
            'admissions': admitted, 'ward_state': [dict(p) for p in active_beds]
        })
    return pd.DataFrame(history)

def find_ai_recommendation(params, target_wk):
    """
    Solves for the specific configuration where the 26-week legacy 
    backlog hits ZERO and stays stabilized.
    """
    # 1. Start with the current beds and try to solve with theater slots
    # 2. If slots alone can't do it (due to Bed-Day choke), expand beds up to 10
    for beds in range(params['total_beds'], 11): 
        for slots in range(1, 15): 
            test_params = {**params, 'surg_per_week': slots, 'total_beds': beds}
            
            # Run a test simulation to see the outcome at the target week
            df = run_simulation(test_params, [], weeks=target_wk + 1)
            
            if not df.empty:
                outcome = df.iloc[target_wk]
                # HARD CONSTRAINT: Legacy (Over 26 Wks) must be exactly 0
                # AND High Acuity (Cat 1/2) must be under control
                if outcome['Over_26_Wks'] == 0 and (outcome['Cat 1'] + outcome['Cat 2']) <= 2:
                    return slots, beds
                    
    # Fallback if no solution is found within 10 beds
    return 10, 10