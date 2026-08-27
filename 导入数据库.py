import os
import ctypes
from ctypes import wintypes
import pandas as pd
import sqlite3
from datetime import date

# ========== 0. 弹窗选择Excel文件（Windows原生API）==========
class OPENFILENAME(ctypes.Structure):
    _fields_ = [
        ('lStructSize', wintypes.DWORD),
        ('hwndOwner', wintypes.HWND),
        ('hInstance', wintypes.HINSTANCE),
        ('lpstrFilter', wintypes.LPCWSTR),
        ('lpstrCustomFilter', wintypes.LPWSTR),
        ('nMaxCustFilter', wintypes.DWORD),
        ('nFilterIndex', wintypes.DWORD),
        ('lpstrFile', wintypes.LPWSTR),
        ('nMaxFile', wintypes.DWORD),
        ('lpstrFileTitle', wintypes.LPWSTR),
        ('nMaxFileTitle', wintypes.DWORD),
        ('lpstrInitialDir', wintypes.LPCWSTR),
        ('lpstrTitle', wintypes.LPCWSTR),
        ('Flags', wintypes.DWORD),
        ('nFileOffset', wintypes.WORD),
        ('nFileExtension', wintypes.WORD),
        ('lpstrDefExt', wintypes.LPCWSTR),
        ('lCustData', wintypes.LPARAM),
        ('lpfnHook', wintypes.LPVOID),
        ('lpTemplateName', wintypes.LPCWSTR),
        ('pvReserved', wintypes.LPVOID),
        ('dwReserved', wintypes.DWORD),
        ('FlagsEx', wintypes.DWORD),
    ]

def pick_file(title='选择Excel文件', filter_str='Excel文件\0*.xlsx;*.xlsm\0所有文件\0*.*\0'):
    ofn = OPENFILENAME()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAME)
    ofn.lpstrFilter = filter_str
    file_buf = ctypes.create_unicode_buffer(260)
    ofn.lpstrFile = ctypes.cast(file_buf, wintypes.LPWSTR)
    ofn.nMaxFile = 260
    ofn.lpstrTitle = title
    ofn.Flags = 0x00001000 | 0x00000800  # OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST
    if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
        return file_buf.value
    return ''

SRC = pick_file(title='选择测试Excel文件')
if not SRC:
    print('未选择文件，程序退出。')
    raise SystemExit

DB_PATH = os.path.join(os.path.dirname(SRC), '业务数据库.db')
today = str(date.today())

# ========== 1. 读取Excel各表 ==========
print(f'[1/7] 读取商品描述、division表 ...', end=' ', flush=True)
master = pd.read_excel(SRC, sheet_name='商品描述、division', header=0)
master = master[['Article', 'Article Name', 'Division']].dropna(subset=['Article'])
master = master.drop_duplicates(subset='Article', keep='first')
master['导入日期'] = today
print(f'完成，{len(master)} 条主数据')

print(f'[2/7] 读取净金额、数量表 ...', end=' ', flush=True)
sales = pd.read_excel(SRC, sheet_name='净金额、数量', header=0)
sales = sales[sales['商品编号'].astype(str).str.startswith('GD')]
sales['净金额'] = sales['净金额'].abs()
sales['数量'] = sales['数量'].abs()
sales['导入日期'] = today
print(f'完成，{len(sales)} 条销售流水')

print(f'[3/7] 读取出样表 ...', end=' ', flush=True)
cy = pd.read_excel(SRC, sheet_name='出样', header=0)
cy['导入日期'] = today
print(f'完成，{len(cy)} 条出样记录')

print(f'[4/7] 读取库存表（清洗中，13万行较大请稍候）...', end=' ', flush=True)
inv_raw = pd.read_excel(SRC, sheet_name='库存', header=None)
h1_idx = inv_raw.index[inv_raw.eq('物料编号').any(axis=1)][0]
h2_idx = h1_idx + 1
inv_data = inv_raw.iloc[h2_idx + 1:]
inv = inv_data.iloc[:, [2, 11, 19]].copy()
inv.columns = ['物料编号', '尺寸', '库存量']
inv = inv[inv['物料编号'].astype(str).str.startswith('GD')].reset_index(drop=True)
inv['库存量'] = pd.to_numeric(inv['库存量'], errors='coerce')
inv['导入日期'] = today
print(f'完成，{len(inv)} 行库存数据')

# ========== 2. 计算成果表 ==========
print(f'[5/7] 汇总成果表 ...', end=' ', flush=True)
sales_agg = sales.groupby('商品编号').agg(
    净金额=('净金额', 'sum'),
    数量=('数量', 'sum')
).reset_index().rename(columns={'商品编号': '物料编号'})

master_dict = master.set_index('Article')[['Article Name', 'Division']].to_dict('index')
cy['出样'] = cy['收据号'].astype(str) + '|' + cy['数量'].astype(str)
cy_dict = cy.drop_duplicates('物料编号').set_index('物料编号')['出样'].to_dict()

inv_stock = inv.dropna(subset=['库存量'])
stock_dict = inv_stock.groupby('物料编号')['库存量'].sum().to_dict()
inv_stock = inv_stock.copy()
inv_stock['库存尺码'] = inv_stock['尺寸'].astype(str) + '|' + inv_stock['库存量'].astype(int).astype(str)
size_dict = inv_stock.groupby('物料编号')['库存尺码'].apply(lambda s: '、'.join(s)).to_dict()

result = sales_agg.copy()
result['商品描述'] = result['物料编号'].map(lambda x: master_dict.get(x, {}).get('Article Name', ''))
result['Division'] = result['物料编号'].map(lambda x: master_dict.get(x, {}).get('Division', ''))
result['出样'] = result['物料编号'].map(cy_dict)
result['当日库存'] = result['物料编号'].map(stock_dict)
result['库存尺码'] = result['物料编号'].map(size_dict)
result = result[['商品描述', 'Division', '物料编号', '净金额', '数量', '当日库存', '出样', '库存尺码']]
result['导入日期'] = today
print(f'完成，{len(result)} 行')

# ========== 3. 导入数据库 ==========
print(f'[6/7] 导入SQLite数据库 ...', end=' ', flush=True)
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 建表
cur.executescript('''
CREATE TABLE IF NOT EXISTS 商品主数据 (
    物料编号 TEXT, 商品描述 TEXT, Division TEXT, 导入日期 TEXT
);
CREATE TABLE IF NOT EXISTS 销售流水 (
    商品编号 TEXT, 净金额 REAL, 数量 REAL, 导入日期 TEXT
);
CREATE TABLE IF NOT EXISTS 出样记录 (
    物料编号 TEXT, 收据号 TEXT, 数量 REAL, 导入日期 TEXT
);
CREATE TABLE IF NOT EXISTS 库存明细 (
    物料编号 TEXT, 尺寸 TEXT, 库存量 REAL, 导入日期 TEXT
);
CREATE TABLE IF NOT EXISTS 成果表 (
    商品描述 TEXT, Division TEXT, 物料编号 TEXT,
    净金额 REAL, 数量 REAL, 当日库存 REAL,
    出样 TEXT, 库存尺码 TEXT, 导入日期 TEXT
);
''')

# 导入前检查是否当天已导入（去重）
for table in ['商品主数据', '销售流水', '出样记录', '库存明细', '成果表']:
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE 导入日期 = ?", (today,))
    existing = cur.fetchone()[0]
    if existing > 0:
        cur.execute(f"DELETE FROM {table} WHERE 导入日期 = ?", (today,))
        conn.commit()

# 批量插入
master_db = master[['Article', 'Article Name', 'Division', '导入日期']].copy()
master_db.columns = ['物料编号', '商品描述', 'Division', '导入日期']
master_db.to_sql('商品主数据', conn, if_exists='append', index=False)
sales[['商品编号', '净金额', '数量', '导入日期']].to_sql(
    '销售流水', conn, if_exists='append', index=False)
cy[['物料编号', '收据号', '数量', '导入日期']].to_sql(
    '出样记录', conn, if_exists='append', index=False)
inv[['物料编号', '尺寸', '库存量', '导入日期']].to_sql(
    '库存明细', conn, if_exists='append', index=False)
result.to_sql(
    '成果表', conn, if_exists='append', index=False)

conn.commit()

# 统计入库行数
counts = {}
for table in ['商品主数据', '销售流水', '出样记录', '库存明细', '成果表']:
    counts[table] = cur.execute(f"SELECT COUNT(*) FROM {table} WHERE 导入日期 = ?", (today,)).fetchone()[0]

conn.close()
print(f'完成')

# ========== 4. 同时输出Excel（保留原功能）==========
print(f'[7/7] 保存Excel文件 ...', end=' ', flush=True)
OUT_RESULT = os.path.join(os.path.dirname(SRC), '成果_输出.xlsx')
OUT_DETAIL = os.path.join(os.path.dirname(SRC), '库存_明细.xlsx')
inv[['物料编号', '尺寸', '库存量']].to_excel(OUT_DETAIL, sheet_name='库存_明细', index=False)
result.drop(columns=['导入日期']).to_excel(OUT_RESULT, sheet_name='成果', index=False)
print(f'完成')

print(f'''
========== 汇总 ==========
数据库路径:       {DB_PATH}

各表入库行数（当日）:
  商品主数据:     {counts['商品主数据']}
  销售流水:       {counts['销售流水']}
  出样记录:       {counts['出样记录']}
  库存明细:       {counts['库存明细']}
  成果表:         {counts['成果表']}

Excel文件:
  明细表:         {OUT_DETAIL}
  成果表:         {OUT_RESULT}

数据库5张表:
  商品主数据(物料编号, 商品描述, Division, 导入日期)
  销售流水(商品编号, 净金额, 数量, 导入日期)
  出样记录(物料编号, 收据号, 数量, 导入日期)
  库存明细(物料编号, 尺寸, 库存量, 导入日期)
  成果表(商品描述, Division, 物料编号, 净金额, 数量, 当日库存, 出样, 库存尺码, 导入日期)
''')
print(result.head(10).to_string(index=False))
