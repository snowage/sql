import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import pandas as pd
import json
import re
import datetime
import requests
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import sqlite3

# 製品リスト読み込み
list = pd.read_csv("list.csv")

# Streamlit CloudのSecretsからGeminiAPIキーを取得してモデルを初期化する関数
def get_gemini_model():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return genai.GenerativeModel('gemini-1.5-flash')
    except KeyError:
        st.error("Gemini APIキーが Streamlit Cloud の Secrets に設定されていません。")
        return None

# GeminiAPIを使用して画像から情報を抽出する関数
def extract_info_with_gemini(model, image_bytes):
    if model is None:
        return None
    prompt = """この画像から、以下の情報を抽出して、JSON形式で出力してください。
    抽出する情報:
    - 型番
    - 製造年
    - 定格能力(冷房) (単位も含む)
    - 定格能力(暖房標準) (単位も含む)
    - 定格能力(暖房低温) (単位も含む)
    - 定格消費電力(冷房) (単位も含む)
    - 定格消費電力(暖房標準) (単位も含む)
    - 定格消費電力(暖房低温) (単位も含む)

    出力例:
    {
        "型番": "...",
        "製造年": "...",
        "定格能力(冷房)": "...",
        "定格能力(暖房標準)": "...",
        "定格能力(暖房低温)": "...",
        "定格消費電力(冷房)": "...",
        "定格消費電力(暖房標準)": "...",
        "定格消費電力(暖房低温)": "..."
    }
    """
    response = model.generate_content(
        [prompt, {"mime_type": "image/jpeg", "data": image_bytes}]
    )
    response_text = response.text.strip() #前後の空白を削除

    # `json プレフィックスと ` サフィックスを取り除く
    response_text = re.sub(r'^```json', '', response_text) #先頭や末尾にある可能性のあるjsonを削除
    response_text = re.sub(r'```$', '', response_text).strip() #前後の空白を削除

    if not response_text:
        st.error("Gemini API からの応答が空です。")
        return None

    try:
        # Gemini の応答が JSON 形式であると期待して解析
        extracted_data = json.loads(response_text)
        return extracted_data
    except Exception as e:
        st.error(f"抽出結果の解析に失敗しました: {e}\n応答内容: {response_text}")
        return None

# 定格能力(kW)を畳数に変換する関数
def kw_size_trans(rated_cooling_capacity):
    if rated_cooling_capacity <= 2.2:
        return 6
    elif rated_cooling_capacity <= 2.5:
        return 8
    elif rated_cooling_capacity <= 2.8:
        return 10
    elif rated_cooling_capacity <= 3.6:
        return 12
    elif rated_cooling_capacity <= 4.5:
        return 14
    else:
        return 16

# 省エネルギー性能・定格能力(冷房)・製造後経過年数から補助金額を算出する関数
def get_points(energy_efficient, cooling_capacity, years_passed):
  if energy_efficient >= 3.0 and cooling_capacity >= 3.6 and years_passed >= 15:
    return 70000
  elif energy_efficient >= 3.0 and cooling_capacity >= 3.6 and years_passed < 15:
    return 23000
  elif energy_efficient >= 3.0 and 2.4 <= cooling_capacity < 3.6 and years_passed >= 15:
    return 60000
  elif energy_efficient >= 3.0 and 2.4 <= cooling_capacity < 3.6 and years_passed < 15:
    return 18000
  elif energy_efficient >= 3.0 and cooling_capacity < 2.4 and years_passed >= 15:
    return 50000
  elif energy_efficient >= 3.0 and cooling_capacity < 2.4 and years_passed < 15:
    return 15000
  elif 2.0 <= energy_efficient < 3.0  and cooling_capacity >= 3.6 and years_passed >= 15:
    return 40000
  elif 2.0 <= energy_efficient < 3.0 and cooling_capacity >= 3.6 and years_passed < 15:
    return 23000
  elif 2.0 <= energy_efficient < 3.0 and 2.4 <= cooling_capacity < 3.6 and years_passed >= 15:
    return 30000
  elif 2.0 <= energy_efficient < 3.0 and 2.4 <= cooling_capacity < 3.6 and years_passed < 15:
    return 10000
  elif 2.0 <= energy_efficient < 3.0 and cooling_capacity < 2.4 and years_passed >= 15:
    return 20000
  elif 2.0 <= energy_efficient < 3.0 and cooling_capacity < 2.4 and years_passed < 15:
    return 9000
  else:
    return("対象外")

# 郵便番号から住所を取得する関数
def get_address(zip_code):
  res = requests.get("https://zipcloud.ibsnet.co.jp/api/search",
                   params={"zipcode":str(zip_code)})
  data = res.json()["results"][0]
  address = data["address1"] + data["address2"] + data["address3"]
  return address

# SQLiteデータベースを初期化する関数
def init_db():
    conn = sqlite3.connect("customer_info.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_number TEXT,
            manufacture_year INTEGER,
            zip_code TEXT,
            address TEXT,
            name TEXT,
            phone_number TEXT,
            email TEXT,
            customer_number TEXT
        )
    """)
    conn.commit()
    conn.close()

# 顧客情報をデータベースに挿入する関数
def add_customer_info(model_number, manufacture_year, zip_code, address, name, phone_number, email, customer_number):
    conn = sqlite3.connect("customer_info.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO customers (model_number, manufacture_year, zip_code, address, name, phone_number, email, customer_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (model_number, manufacture_year, zip_code, address, name, phone_number, email, customer_number))
    conn.commit()
    conn.close()

# メールアドレスをキーに顧客情報を検索する関数
def get_customer_info(email):
    conn = sqlite3.connect("customer_info.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE email = ?", (email,))
    customer_info = cursor.fetchone()
    conn.close()
    return customer_info

# 以下streamlitの出力
def main():
    st.title("エアコン補助金・見積自動判定")

    # データベースの初期化