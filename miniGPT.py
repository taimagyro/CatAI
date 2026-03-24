from flask import Flask, request, Response
import json

app = Flask(__name__)

# 簡単な記憶
knowledge = {}
last_question = None

# AIの返答
def generate(text):
    for q in knowledge:
        if q in text:
            return knowledge[q]
    return "わかりません。教えてください"

@app.route("/chat", methods=["POST"])
def chat():
    global last_question

    data = request.get_json()
    user_input = data.get("message", "")

    # 教えてもらうモード
    if last_question:
        knowledge[last_question] = user_input
        last_question = None

        return Response(
            json.dumps({"reply": "覚えました！"}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )

    # 普通の応答
    reply = generate(user_input)

    # わからない場合は次に教えてもらう
    if reply == "わかりません。教えてください":
        last_question = user_input

    return Response(
        json.dumps({"reply": reply}, ensure_ascii=False),
        content_type="application/json; charset=utf-8"
    )

# Render対応
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
