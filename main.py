import os
import streamlit as st
import openai
from typing import List, Dict, Any
from swarm import Swarm, Agent

# ─ APIキー設定 ─────────────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key")
if not api_key:
    st.error("OpenAI APIキーが設定されていません。設定を確認してください。")
    st.stop()
openai.api_key = api_key
os.environ["OPENAI_API_KEY"] = api_key

# ─ Swarm クライアント & エージェント定義 ─────────────────────────
client = Swarm()


def transfer_to_facilitator_agent():
    return facilitator_agent


def transfer_to_idea_agent():
    return Agent(
        name="IdeaAgent",
        instructions="あなたはIdeaAgentです。与えられたテーマに沿って創造的かつ実現可能なアイデアを提案してください。",
        functions=[transfer_to_facilitator_agent],
        sender="IdeaAgent",
    )


def transfer_to_analysis_agent():
    return Agent(
        name="AnalysisAgent",
        instructions="あなたはAnalysisAgentです。提供されたアイデアについて利点と欠点を分析してください。",
        functions=[transfer_to_facilitator_agent],
        sender="AnalysisAgent",
    )


def transfer_to_summary_agent():
    return Agent(
        name="SummaryAgent",
        instructions="あなたはSummaryAgentです。これまでの議論を簡潔にまとめ、次ステップを提案してください。",
        functions=[transfer_to_facilitator_agent],
        sender="SummaryAgent",
    )


facilitator_agent = Agent(
    name="Facilitator",
    instructions="""
あなたはファシリテーターです。ユーザーの質問に対して、適切なエージェントに転送します。
アイディアの提案が必要な時はtransfer_to_idea_agentを呼び出してください。
分析が必要な時はtransfer_to_analysis_agentを呼び出してください。
まとめが必要な時はtransfer_to_summary_agentを呼び出してください。
掘り下げが必要な場合はあなたが掘り下げてください。掘り下げた後は他のエージェントに転送してください。
""",
    functions=[
        transfer_to_idea_agent,
        transfer_to_analysis_agent,
        transfer_to_summary_agent,
    ],
    sender="Facilitator",
)


# ─ run_agent ヘルパー関数 ─────────────────────────────────────
def run_agent(agent: Agent, history: List[Dict[str, Any]]) -> str:
    response = client.run(agent=agent, messages=history)

    # メッセージを処理
    messages = []
    # ジェネレータをリストに変換
    response_messages = list(response)

    # messagesタプルを探す
    for item in response_messages:
        if isinstance(item, tuple) and item[0] == "messages":
            message_list = item[1]
            for m in message_list:
                # contentがNoneでない場合のみ追加
                if m.get("content") is not None:
                    content = m.get("content", "")
                    # JSON文字列の場合はスキップ
                    if not content.startswith('{"assistant": "'):
                        # メッセージの内容から送信者を判断
                        sender = m.get("sender", agent.name)
                        # メッセージの先頭に "AgentName: " の形式がある場合、その名前を送信者として使用
                        if ":" in content.split("\n")[0]:
                            sender = content.split("\n")[0].split(":")[0].strip()
                        messages.append({"content": content, "sender": sender})

    # メッセージがない場合は空文字列を返す
    if not messages:
        return ""

    # 重複を除去して結合
    unique_messages = []
    seen_contents = set()
    for msg in messages:
        if msg["content"] not in seen_contents:
            seen_contents.add(msg["content"])
            unique_messages.append(msg)

    # メッセージを結合して返す
    return "\n".join(f"{msg['sender']}: {msg['content']}" for msg in unique_messages)


# ─ Streamlit UI 設定 ────────────────────────────────────────────
st.set_page_config(page_title="壁打ちチャット with Swarm🐝", layout="wide")
st.title("🗨️ 壁打ちチャット with Swarm🐝")

# セッションステート初期化
if "messages" not in st.session_state:
    st.session_state.messages: List[Dict[str, str]] = []  # type: ignore
if "user_input" not in st.session_state:
    st.session_state.user_input = ""


# ─ 入力フォーム ─────────────────────────────────────────────────
with st.sidebar:
    user_input = st.text_area(
        "あなたの意見を入力",
        value=st.session_state.user_input,
        height=100,
        key="user_input_area",
    )
    send = st.button("送信")
    next_btn = st.button("Next")


# ─ 会話処理 ──────────────────────────────────────────────────────
def process_conversation(user_msg: str = None):
    # ユーザー発言を履歴に追加
    if user_msg:
        st.session_state.messages.append({"sender": "You", "content": user_msg})
    # 会話履歴を role/content 形式に変換
    history = [
        {
            "role": "user" if m["sender"] == "You" else "assistant",
            "content": m["content"],
        }
        for m in st.session_state.messages
    ]
    # ファシリテーター実行
    fac_output = run_agent(facilitator_agent, history)
    st.session_state.messages.append({"sender": "Facilitator", "content": fac_output})


# ─ ボタン処理 ─────────────────────────────────────────────────
if send and user_input:
    process_conversation(user_input)
    # テキストエリアをクリア
    st.session_state.user_input = ""
    # ページをリロードして反映
    st.rerun()
elif next_btn:
    process_conversation()

# ─ チャット表示 ─────────────────────────────────────────────────
for msg in st.session_state.messages:
    print("--------------------------------")
    print(msg)
    print("--------------------------------")

    align = "right" if msg["sender"] == "You" else "left"
    bg = "#DCF8C6" if msg["sender"] == "You" else "#FFF"
    border = "" if msg["sender"] == "You" else "1px solid #EEE"

    # 送信者の表示を改善
    sender = msg["sender"]
    content = msg.get("content", "")
    if isinstance(content, str) and ":" in content:
        sender_candidate = content.split(":")
        if sender_candidate:
            sender = sender_candidate[0].strip()

    sender_html = f"<strong>{sender}</strong><br>" if sender != "You" else ""

    # コンテンツの処理
    # senderが存在する場合はsender:を削除
    prefix = f"{sender}:"
    if content.startswith(prefix):
        content = content[len(prefix) :]

    # 不要な改行を削除し、重複を除去
    content = "\n".join(
        dict.fromkeys(line for line in content.split("\n") if line.strip())
    )

    # 空のメッセージは表示しない
    if not content.strip():
        continue

    bubble_html = (
        f'<div style="text-align:{align}; margin:5px;">'
        f'<span style="background-color:{bg}; padding:8px; border-radius:10px; display:inline-block; max-width:70%; white-space:pre-wrap; border:{border};">'
        f"{sender_html}{content}"
        f"</span></div>"
    )
    st.markdown(bubble_html, unsafe_allow_html=True)
