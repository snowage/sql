import sqlite3
import datetime
import pandas as pd

class DatabaseManager:
    def __init__(self, db_file):
        """データベース接続を初期化し、必要なテーブルを作成する"""
        self.db_file = db_file
        self._create_tables()

    def _get_connection(self):
        """データベース接続を返す"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        """必要なテーブルを作成する"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # customers テーブルの作成
        cursor.execute('''
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
        ''')

        conn.commit()
        conn.close()

    def add_customer_info(self, model_number, manufacture_year, zip_code, address, name, phone_number, email, customer_number):
        """顧客情報をデータベースに追加する"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO customers (model_number, manufacture_year, zip_code, address, name, phone_number, email, customer_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (model_number, manufacture_year, zip_code, address, name, phone_number, email, customer_number))

        conn.commit()
        conn.close()

    def get_customer_info(self, email):
        """メールアドレスをキーに顧客情報を検索する"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE email = ?", (email,))
        customer_info = cursor.fetchone()
        conn.close()
        return customer_info