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
            part_name TEXT,
            stock_quantity REAL DEFAULT 0.0,
            inbound_quantity REAL DEFAULT 0.0
        )
    ''')
    
    # 品番と日付の複合ユニークインデックス（重複インポート時の上書きに必要）
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_part_date 
        ON actual_records (part_number, date)
    ''')
    
    # 仕入価格マスタテーブルの作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_price_master (
            part_number TEXT PRIMARY KEY,
            purchase_price REAL NOT NULL
        )
    ''')
    
    # 販売価格マスタテーブルの作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_price_master (
            part_number TEXT PRIMARY KEY,
            sales_price REAL NOT NULL
        )
    ''')
    
    # 既存テーブルへのカラム追加（すでに存在する場合はエラーを無視する）
    try:
        cursor.execute("ALTER TABLE actual_records ADD COLUMN inbound_quantity REAL DEFAULT 0")
    except:
        pass
        
    try:
        cursor.execute("ALTER TABLE actual_records ADD COLUMN stock_quantity REAL DEFAULT 0")
    except:
        pass
    
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
        INSERT OR REPLACE INTO actual_records (part_number, date, quantity, part_name, stock_quantity, inbound_quantity)
        VALUES (?, ?, ?, ?, ?, ?)
    '''
    
    for rec in records:
        part_number = str(rec.get('part_number', '')).strip()
        date = str(rec.get('date', '')).strip()
        
        try:
            quantity = float(rec.get('quantity', 0))
        except (ValueError, TypeError):
            quantity = 0.0
            
        try:
            stock_quantity = float(rec.get('stock_quantity', 0))
        except (ValueError, TypeError):
            stock_quantity = 0.0
            
        try:
            inbound_quantity = float(rec.get('inbound_quantity', 0))
        except (ValueError, TypeError):
            inbound_quantity = 0.0
            
        part_name = rec.get('part_name', '')
        if part_name:
            part_name = str(part_name).strip()
        else:
            part_name = ''
            
        # 必須フィールドのチェック
        if not part_number or not date:
            skip_count += 1
            continue
            
        cursor.execute(query, (part_number, date, quantity, part_name, stock_quantity, inbound_quantity))
        success_count += 1
        
    conn.commit()
    conn.close()
    
    return success_count, skip_count

def save_purchase_prices(records):
    """
    仕入価格データをデータベースに保存または更新します。
    (品番) が重複する場合は、自動的に上書き (REPLACE) します。
    records: 辞書のリスト。各要素は {'part_number': str, 'purchase_price': float}
    returns: 処理された件数
    """
    if not records:
        return 0
        
    conn = get_connection()
    cursor = conn.cursor()
    
    count = 0
    query = '''
        INSERT OR REPLACE INTO purchase_price_master (part_number, purchase_price)
        VALUES (?, ?)
    '''
    
    for rec in records:
        part_number = str(rec.get('part_number', '')).strip()
        try:
            purchase_price = float(rec.get('purchase_price', 0))
        except (ValueError, TypeError):
            continue
            
        if not part_number:
            continue
            
        cursor.execute(query, (part_number, purchase_price))
        count += 1
        
    conn.commit()
    conn.close()
    
    return count

def save_sales_prices(records):
    """
    販売価格データをデータベースに保存または更新します。
    (品番) が重複する場合は、自動的に上書き (REPLACE) します。
    records: 辞書のリスト。各要素は {'part_number': str, 'sales_price': float}
    returns: 処理された件数
    """
    if not records:
        return 0
        
    conn = get_connection()
    cursor = conn.cursor()
    
    count = 0
    query = '''
        INSERT OR REPLACE INTO sales_price_master (part_number, sales_price)
        VALUES (?, ?)
    '''
    
    for rec in records:
        part_number = str(rec.get('part_number', '')).strip()
        try:
            sales_price = float(rec.get('sales_price', 0))
        except (ValueError, TypeError):
            continue
            
        if not part_number:
            continue
            
        cursor.execute(query, (part_number, sales_price))
        count += 1
        
    conn.commit()
    conn.close()
    
    return count


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

def get_unique_part_names():
    """
    データベースに登録されているユニークな品名の一覧を取得します。
    空文字や「品名未登録」は除外します。
    """
    conn = get_connection()
    query = '''
        SELECT DISTINCT part_name 
        FROM actual_records 
        WHERE part_name IS NOT NULL AND part_name != '' AND part_name != '品名未登録'
        ORDER BY part_name ASC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df['part_name'].tolist()

def search_parts_by_name(selected_name=None, keyword=None):
    """
    指定された品名またはキーワードに合致する品番のリストを取得します。
    """
    conn = get_connection()
    
    query = 'SELECT DISTINCT part_number FROM actual_records WHERE 1=1'
    params = []
    
    if selected_name:
        query += ' AND part_name = ?'
        params.append(selected_name)
        
    if keyword:
        # LIKE検索で部分一致
        query += ' AND part_name LIKE ?'
        params.append(f'%{keyword}%')
        
    query += ' ORDER BY part_number ASC'
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df['part_number'].tolist()

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
            return pd.DataFrame(columns=['date', 'part_number', 'part_name', 'quantity', 'inbound_quantity', 'stock_quantity', 'sales_price', 'purchase_price', 'sales_amount', 'cost_amount', 'gross_profit', 'gross_margin'])
        placeholders = ','.join(['?'] * len(part_number))
        query = f'''
            SELECT a.date, a.part_number, a.part_name, a.quantity, a.inbound_quantity, a.stock_quantity,
                   s.sales_price, p.purchase_price
            FROM actual_records a
            LEFT JOIN sales_price_master s ON a.part_number = s.part_number
            LEFT JOIN purchase_price_master p ON a.part_number = p.part_number
            WHERE a.part_number IN ({placeholders})
        '''
        params = list(part_number)
    else:
        query = '''
            SELECT a.date, a.part_number, a.part_name, a.quantity, a.inbound_quantity, a.stock_quantity,
                   s.sales_price, p.purchase_price
            FROM actual_records a
            LEFT JOIN sales_price_master s ON a.part_number = s.part_number
            LEFT JOIN purchase_price_master p ON a.part_number = p.part_number
            WHERE a.part_number = ?
        '''
        params = [part_number]
    
    if start_date:
        query += ' AND a.date >= ?'
        params.append(start_date)
        
    if end_date:
        query += ' AND a.date <= ?'
        params.append(end_date)
        
    query += ' ORDER BY a.date ASC'
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if not df.empty:
        df['sales_price'] = df['sales_price'].fillna(0)
        df['purchase_price'] = df['purchase_price'].fillna(0)
        df['sales_amount'] = df['quantity'] * df['sales_price']
        df['cost_amount'] = df['quantity'] * df['purchase_price']
        df['gross_profit'] = df['sales_amount'] - df['cost_amount']
        df['gross_margin'] = df.apply(lambda row: row['gross_profit'] / row['sales_amount'] if row['sales_amount'] != 0 else 0.0, axis=1)
    else:
        df['sales_amount'] = 0.0
        df['cost_amount'] = 0.0
        df['gross_profit'] = 0.0
        df['gross_margin'] = 0.0
        
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

def clear_purchase_price_master():
    """
    仕入価格マスタ（purchase_price_master）の全データを消去します。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM purchase_price_master')
    conn.commit()
    conn.close()

def clear_db():
    """
    データベースの実績データなど全データを消去します。
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
