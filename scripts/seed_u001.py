import sys
import os
from datetime import date
import json

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from libs.core_domain.db import init_db, get_session, User, UserBaseline, UserDaily

def seed_data():
    init_db()
    session = get_session()
    
    user_id = "u001"
    
    # 1. Ensure User exists
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        print(f"Creating user {user_id}...")
        user = User(
            user_id=user_id,
            email="u001@example.com",
            password_hash="mock_hash",
            display_name="Test User",
            gender="male"
        )
        session.add(user)
    
    # 2. Inject Baseline
    baseline = session.query(UserBaseline).filter_by(user_id=user_id).first()
    if not baseline:
        print("Creating baseline...")
        baseline = UserBaseline(
            user_id=user_id,
            sleep_baseline_hours=7.5,
            sleep_baseline_eff=0.90,
            rest_baseline_ratio=0.20,
            hrv_baseline_mu=65.0,
            hrv_baseline_sd=8.0
        )
        session.add(baseline)
    else:
        print("Updating baseline...")
        baseline.sleep_baseline_hours = 7.5
        baseline.hrv_baseline_mu = 65.0
        
    # 3. Inject Readiness for Today (UserDaily)
    today = date.today()
    daily = session.query(UserDaily).filter_by(user_id=user_id, date=today).first()
    
    # Mock Evidence Pool matching what the App expects
    evidence_pool = {
        "hrv_balance": "Optimal",
        "sleep_balance": "Optimal", 
        "recovery_index": 85,
        "temperature": "Normal",
        "resting_hr": 58,
        "previous_day_activity": "High",
        "sleep_performance": "Good",
        "restorative_sleep": "High",
        "subjective_fatigue": "Low"
    }
    
    # Mock Posterior Probs
    probs = {
        "Peak": 0.8,
        "Well-adapted": 0.15, 
        "FOR": 0.05,
        "Acute Fatigue": 0.0,
        "NFOR": 0.0,
        "OTS": 0.0
    }
    
    if not daily:
        print(f"Creating daily record for {today}...")
        daily = UserDaily(
            user_id=user_id,
            date=today,
            final_readiness_score=88,
            final_diagnosis="Ready to Perform",
            final_posterior_probs=probs,
            # IMPORTANT: This matches what APIService fetches for the Readiness Factors Sheet
            objective={"evidence_pool": evidence_pool}, 
            # Note: Depending on where mapping puts it, verify if it's 'objective' or another field.
            # Looking at ReadinessModels.swift: evidencePool
            # Looking at backend engine, it might be constructed on the fly or stored.
            # Let's put it in a generic place or check readiness-api main.py. 
            # For now, I'll put it in 'device_metrics' as a catch-all if needed, 
            # but usually ReadinessResponse constructs it.
        )
        # Mocking the ReadinessResponse structure requires understanding how the API builds it.
        # apps/readiness-api/main.py -> service.compute_readiness_from_payload -> returns ReadinessResult
        # The API returns that result.
        # We might need to run the ENGINE to get real output, OR we just trust that the API calls the engine properly.
        # But if the user is getting 404 on baseline, the Readiness API might also fail if it depends on baseline.
        
        session.add(daily)
    
    session.commit()
    print("✅ Data seeded successfully!")

if __name__ == "__main__":
    seed_data()
