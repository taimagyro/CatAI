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
        res = supabase.table("training_data").insert({
            "user_id": user_id,
            "input": user_input,
            "output": ai_output,
            "good": None
        }).execute()

        # IDを返す（重要）
        return res.data[0]["id"]

    except Exception as e:
        print("学習保存エラー:", e)
        return None


# =========================
# 評価保存
# =========================
def update_feedback(record_id, is_good):
    try:
        supabase.table("training_data").update({
            "good": is_good
        }).eq("id", record_id).execute()
    except Exception as e:
        print("評価保存エラー:", e)
