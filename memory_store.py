from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# 学習データ保存
# =========================
def save_training(user_id, user_input, ai_output):
    res = supabase.table("training_data").insert({
        "user_id": user_id,
        "input": user_input,
        "output": ai_output,
        "good": None,
        "reason": None
    }).execute()

    return res.data[0]["id"]

# =========================
# フィードバック更新
# =========================
def update_feedback(record_id, good, reason=None):
    supabase.table("training_data").update({
        "good": good,
        "reason": reason
    }).eq("id", record_id).execute()
