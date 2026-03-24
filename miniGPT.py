
from flask import Flask, request, jsonify

app = Flask(__name__)

# 知識（最初は少ない）
knowledge = {}

# AIの返答
def generate(text):

    # すでに知っているか
    for q in knowledge:
        if q in text:
            return knowledge[q]

    # わからない場合
    return "わかりません。教えてください"

@app.route("/chat", methods=["POST"])
def chat():

    data = request.json
    user_input = data["message"]

    # 前の質問を覚える
    global last_question

    if "last_question" in globals() and last_question:

        knowledge[last_question] = user_input
        last_question = None
        return jsonify({"reply":"覚えました！"})

    # 普通の応答
    reply = generate(user_input)

    if reply == "わかりません。教えてください":
        last_question = user_input

    return jsonify({"reply":reply})

app.run(port=5000)
