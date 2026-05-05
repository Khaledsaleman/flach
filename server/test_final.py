import requests
import json
import time

BASE_URL = "http://localhost:5000"
USER_ID = "final_test_user"

def test_full_cycle():
    print("1. Testing Registration and Full State persistence...")
    resp = requests.post(f"{BASE_URL}/check-status", json={"user_id": USER_ID, "username": "Final User"})
    data = resp.json()
    user = data['user']
    print(f"   Initial Gold: {user['balance']['gold']}, Energy: {user['energy']}, Rank: {user['rank']}")

    print("\n2. Testing Progress Saving (Spend gold, lose energy)...")
    new_balance = {"gold": 75.0, "ton": 0.0, "usdt": 0.0}
    buildings = [{"type": "goldMine", "level": 1, "col": 1, "row": 1}]
    resp = requests.post(f"{BASE_URL}/buildings/save", json={
        "user_id": USER_ID,
        "buildings": buildings,
        "balance": new_balance,
        "energy": 90,
        "rank": "فضي I"
    })
    print(f"   Save Status: {resp.json()['status']}")

    print("\n3. Testing Retrieval after Save...")
    resp = requests.post(f"{BASE_URL}/check-status", json={"user_id": USER_ID})
    user = resp.json()['user']
    print(f"   Stored Gold: {user['balance']['gold']} (Expected ~75)")
    print(f"   Stored Energy: {user['energy']} (Expected 90)")
    print(f"   Stored Rank: {user['rank']} (Expected فضي I)")
    print(f"   Stored Buildings: {len(user['buildings'])} (Expected 1)")

    if abs(user['balance']['gold'] - 75.0) < 1.0 and user['energy'] == 90 and user['rank'] == "فضي I" and len(user['buildings']) == 1:
        print("\nSUCCESS: All data persisted correctly!")
    else:
        print("\nFAIL: Persistence issues detected.")

if __name__ == "__main__":
    test_full_cycle()
