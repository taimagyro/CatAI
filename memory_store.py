from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# 学習データ保存
# =========================
def save_training(user_id, user_input, ai_output):
    try:
        supabase.table("training_data").insert({
            "user_id": user_id,
            "input": user_input,
            "output": ai_output
        }).execute()
    except Exception as e:
        print("学習保存エラー:", e)
