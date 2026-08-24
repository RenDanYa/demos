import os
import ctypes
from ctypes import wintypes
import pandas as pd

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

OUT_RESULT = os.path.join(os.path.dirname(SRC), '成果_输出.xlsx')
OUT_DETAIL = os.path.join(os.path.dirname(SRC), '库存_明细.xlsx')

print(f'[1/6] 读取商品描述、division表 ...', end=' ', flush=True)
master = pd.read_excel(SRC, sheet_name='商品描述、division', header=0)
master = master[['Article', 'Article Name', 'Division']].dropna(subset=['Article'])
master = master.drop_duplicates(subset='Article', keep='first')
master_dict = master.set_index('Article')[['Article Name', 'Division']].to_dict('index')
print(f'完成，{len(master_dict)} 条主数据')

print(f'[2/6] 读取净金额、数量表 ...', end=' ', flush=True)
sales = pd.read_excel(SRC, sheet_name='净金额、数量', header=0)
sales = sales[sales['商品编号'].astype(str).str.startswith('GD')]
sales_agg = sales.groupby('商品编号').agg(
    净金额=('净金额', 'sum'),
    数量=('数量', 'sum')
).reset_index()
sales_agg['净金额'] = sales_agg['净金额'].abs()
sales_agg['数量'] = sales_agg['数量'].abs()
sales_agg = sales_agg.rename(columns={'商品编号': '物料编号'})
print(f'完成，{len(sales_agg)} 条销售汇总')

print(f'[3/6] 读取出样表 ...', end=' ', flush=True)
cy = pd.read_excel(SRC, sheet_name='出样', header=0)
cy['出样'] = cy['收据号'].astype(str) + '|' + cy['数量'].astype(str)
cy_dict = cy.set_index('物料编号')['出样'].to_dict()
print(f'完成，{len(cy_dict)} 条出样记录')

print(f'[4/6] 读取库存表（清洗中，13万行较大请稍候）...', end=' ', flush=True)
inv_raw = pd.read_excel(SRC, sheet_name='库存', header=None)
h1_idx = inv_raw.index[inv_raw.eq('物料编号').any(axis=1)][0]
h2_idx = h1_idx + 1
inv_data = inv_raw.iloc[h2_idx + 1:]
inv = inv_data.iloc[:, [2, 11, 19]].copy()
inv.columns = ['物料编号', '尺寸', '库存量']
inv = inv[inv['物料编号'].astype(str).str.startswith('GD')].reset_index(drop=True)
inv['库存量'] = pd.to_numeric(inv['库存量'], errors='coerce')
print(f'完成，{len(inv)} 行库存数据')

print(f'  → 提取当日库存 & 库存尺码 ...', end=' ', flush=True)
inv_stock = inv.dropna(subset=['库存量'])
stock_dict = inv_stock.groupby('物料编号')['库存量'].sum().to_dict()
inv_stock = inv_stock.copy()
inv_stock['库存尺码'] = inv_stock['尺寸'].astype(str) + '|' + inv_stock['库存量'].astype(int).astype(str)
size_dict = inv_stock.groupby('物料编号')['库存尺码'].apply(lambda s: '、'.join(s)).to_dict()
print(f'完成，{len(stock_dict)} 个物料有库存')

print(f'[5/6] 汇总成果表 ...', end=' ', flush=True)
result = sales_agg.copy()
result['商品描述'] = result['物料编号'].map(lambda x: master_dict.get(x, {}).get('Article Name', ''))
result['Division'] = result['物料编号'].map(lambda x: master_dict.get(x, {}).get('Division', ''))
result['出样'] = result['物料编号'].map(cy_dict)
result['当日库存'] = result['物料编号'].map(stock_dict)
result['库存尺码'] = result['物料编号'].map(size_dict)
result = result[['商品描述', 'Division', '物料编号', '净金额', '数量', '当日库存', '出样', '库存尺码']]
print(f'完成，{len(result)} 行')

print(f'[6/6] 保存文件 ...', end=' ', flush=True)
inv[['物料编号', '尺寸', '库存量']].to_excel(OUT_DETAIL, sheet_name='库存_明细', index=False)
result.to_excel(OUT_RESULT, sheet_name='成果', index=False)
print(f'完成')

print(f'''
========== 汇总 ==========
物料总数:       {len(result)}
有出样的:       {result['出样'].notna().sum()}
有当日库存的:   {result['当日库存'].notna().sum()}
有库存尺码的:   {result['库存尺码'].notna().sum()}
库存明细行数:   {len(inv)}

明细表已保存: {OUT_DETAIL}
成果表已保存: {OUT_RESULT}
''')
print(result.head(10).to_string(index=False))
