import sqlite3
import os
import pandas as pd

DB_FILE = 'parts_tracker.db'

def get_connection():
    """
    SQLiteデータベースへの接続を取得します。
    Streamlitの並列リクエストに対応するため、timeoutを長めに設定します。
    """
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    データベースとテーブルを初期化します。
    重複登録を防ぐため、品番と日付(年月)のペアにユニークインデックスを設定します。
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 実績レコードテーブルの作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS actual_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT NOT NULL,
            date TEXT NOT NULL,          -- YYYY-MM 形式
            quantity REAL NOT NULL,
            part_name TEXT
        )
    ''')
    
    # 品番と日付の複合ユニークインデックス（重複インポート時の上書きに必要）
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_part_date 
        ON actual_records (part_number, date)
    ''')
    
    conn.commit()
    conn.close()

def save_records(records):
    """
    レコードリストをデータベースに保存または更新します。
    (品番, 日付) が重複する場合は、自動的に上書き (REPLACE) します。
    records: 辞書のリスト。各要素は {'part_number': str, 'date': str, 'quantity': float, 'part_name': str}
    returns: (追加/更新された件数, スキップされた件数)
    """
    if not records:
        return 0, 0
        
    conn = get_connection()
    cursor = conn.cursor()
    
    success_count = 0
    skip_count = 0
    
    # データを一括で INSERT OR REPLACE
    query = '''
        INSERT OR REPLACE INTO actual_records (part_number, date, quantity, part_name)
        VALUES (?, ?, ?, ?)
    '''
    
    for rec in records:
        part_number = str(rec.get('part_number', '')).strip()
        date = str(rec.get('date', '')).strip()
        
        try:
            quantity = float(rec.get('quantity', 0))
        except (ValueError, TypeError):
            quantity = 0.0
            
        part_name = rec.get('part_name', '')
        if part_name:
            part_name = str(part_name).strip()
        else:
            part_name = ''
            
        # 必須フィールドのチェック
        if not part_number or not date:
            skip_count += 1
            continue
            
        cursor.execute(query, (part_number, date, quantity, part_name))
        success_count += 1
        
    conn.commit()
    conn.close()
    
    return success_count, skip_count

def get_unique_parts():
    """
    登録されているすべてのユニークな品番と品名の一覧を取得します。
    品名は、同じ品番で登録されている最新のものを優先します。
    """
    conn = get_connection()
    # 各品番の最新(最大ID)の品名を取得するクエリ
    query = '''
        SELECT part_number, part_name
        FROM actual_records
        GROUP BY part_number
        ORDER BY part_number ASC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df.to_dict('records')

def query_records(part_number, start_date=None, end_date=None):
    """
    指定品番（単一または複数リスト）・期間の実績データを日付順に取得します。
    start_date, end_date は 'YYYY-MM' 形式
    """
    conn = get_connection()
    
    # 複数品番（リストやタプル）に対応
    if isinstance(part_number, (list, tuple)):
        if not part_number:
            conn.close()
            return pd.DataFrame(columns=['date', 'part_number', 'part_name', 'quantity'])
        placeholders = ','.join(['?'] * len(part_number))
        query = f'SELECT date, part_number, part_name, quantity FROM actual_records WHERE part_number IN ({placeholders})'
        params = list(part_number)
    else:
        query = 'SELECT date, part_number, part_name, quantity FROM actual_records WHERE part_number = ?'
        params = [part_number]
    
    if start_date:
        query += ' AND date >= ?'
        params.append(start_date)
        
    if end_date:
        query += ' AND date <= ?'
        params.append(end_date)
        
    query += ' ORDER BY date ASC'
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_db_stats():
    """
    データベースの統計情報（総レコード数、総品番数）を取得します。
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM actual_records')
    total_records = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT part_number) FROM actual_records')
    total_parts = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_records': total_records,
        'total_parts': total_parts
    }

def clear_db():
    """
    データベースの全データを消去します。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM actual_records')
    conn.commit()
    conn.close()

def delete_records_by_month(date):
    """
    指定された年月 (YYYY-MM) の実績レコードをデータベースから一括削除します。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM actual_records WHERE date = ?', (date,))
    conn.commit()
    deleted_count = cursor.rowcount
    conn.close()
    return deleted_count

def get_unique_months():
    """
    蓄積されているデータから、ユニークな年月 (YYYY-MM) の一覧を取得します（降順）。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT date FROM actual_records ORDER BY date DESC')
    months = [row[0] for row in cursor.fetchall()]
    conn.close()
    return months

def has_part(part_number):
    """
    指定された品番がデータベースに1件でも登録されているか確認します。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM actual_records WHERE part_number = ? LIMIT 1', (part_number,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists
