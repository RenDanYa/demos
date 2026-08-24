import pandas as pd

SRC = r'c:\Users\godisgirl\.trae-cn\attachments\6a8bfd85e15d64a332569168\72b3f34c-a8ed-45ba-9b0d-418e8cf14243_测试.xlsx'
OUT = r'd:\obsidian\demo\库存_清洗.xlsx'

raw = pd.read_excel(SRC, sheet_name='库存', header=None)

# 定位双层表头：第一层 = 含"物料编号"的行，第二层 = 其下一行
h1_idx = raw.index[raw.eq('物料编号').any(axis=1)][0]
h2_idx = h1_idx + 1
h1, h2 = raw.iloc[h1_idx], raw.iloc[h2_idx]

# 合并双层表头为单行
cols = []
for c in range(raw.shape[1]):
    a = str(h1[c]).strip() if pd.notna(h1[c]) else ''
    b = str(h2[c]).strip() if pd.notna(h2[c]) else ''
    cols.append('/'.join(x for x in (a, b) if x))

data = raw.iloc[h2_idx + 1:].copy()
data.columns = cols
data = data.loc[:, [c for c in cols if c]]          # 去掉无表头的空列
data = data.dropna(how='all')                        # 去掉全空行
data = data[data['物料编号/品牌'].astype(str).str.startswith('GD')].reset_index(drop=True)

print(f'表头行: 原第{h1_idx + 1}~{h2_idx + 1}行 -> 合并为1行, 共{data.shape[1]}列')
print(f'数据行: {len(data)}')
print(data.head(8).to_string())

data.to_excel(OUT, sheet_name='库存_清洗', index=False)
print(f'\n已保存: {OUT}')
