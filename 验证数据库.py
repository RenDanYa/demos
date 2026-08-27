import sqlite3
import pandas as pd

DB_PATH = r'd:\obsidian\demo\业务数据库.db'
conn = sqlite3.connect(DB_PATH)

print('=' * 60)
print('数据库路径:', DB_PATH)
print('=' * 60)

# 1. 列出所有表
tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn)
print('\n【1】数据库中的表：')
print(tables.to_string(index=False))

# 2. 每张表的行数和字段
print('\n【2】各表行数：')
for t in ['商品主数据', '销售流水', '出样记录', '库存明细', '成果表']:
    cnt = pd.read_sql(f"SELECT COUNT(*) AS 行数 FROM {t}", conn).iloc[0, 0]
    cols = pd.read_sql(f"PRAGMA table_info({t})", conn)
    col_names = ', '.join(cols['name'].tolist())
    print(f'  {t}: {cnt} 行 | 字段: {col_names}')

# 3. 成果表前10行
print('\n【3】成果表前10行：')
result = pd.read_sql("SELECT 商品描述, Division, 物料编号, 净金额, 数量, 当日库存, 出样, 库存尺码 FROM 成果表 LIMIT 10", conn)
print(result.to_string(index=False))

# 4. 商品主数据前5行
print('\n【4】商品主数据前5行：')
master = pd.read_sql("SELECT 物料编号, 商品描述, Division FROM 商品主数据 LIMIT 5", conn)
print(master.to_string(index=False))

# 5. 销售流水前5行
print('\n【5】销售流水前5行：')
sales = pd.read_sql("SELECT 商品编号, 净金额, 数量 FROM 销售流水 LIMIT 5", conn)
print(sales.to_string(index=False))

# 6. 出样记录前5行
print('\n【6】出样记录前5行：')
cy = pd.read_sql("SELECT 物料编号, 收据号, 数量 FROM 出样记录 LIMIT 5", conn)
print(cy.to_string(index=False))

# 7. 库存明细前5行
print('\n【7】库存明细前5行：')
inv = pd.read_sql("SELECT 物料编号, 尺寸, 库存量 FROM 库存明细 LIMIT 5", conn)
print(inv.to_string(index=False))

# 8. 验证数据完整性
print('\n【8】数据完整性验证：')
print(f'  成果表物料数: {pd.read_sql("SELECT COUNT(DISTINCT 物料编号) FROM 成果表", conn).iloc[0,0]}')
print(f'  销售流水去重物料数: {pd.read_sql("SELECT COUNT(DISTINCT 商品编号) FROM 销售流水", conn).iloc[0,0]}')
print(f'  库存明细有库存量物料数: {pd.read_sql("SELECT COUNT(DISTINCT 物料编号) FROM 库存明细 WHERE 库存量 IS NOT NULL", conn).iloc[0,0]}')
print(f'  出样记录去重物料数: {pd.read_sql("SELECT COUNT(DISTINCT 物料编号) FROM 出样记录", conn).iloc[0,0]}')
print(f'  主数据去重物料数: {pd.read_sql("SELECT COUNT(DISTINCT 物料编号) FROM 商品主数据", conn).iloc[0,0]}')

# 9. 验证成果表数据与各源表一致
print('\n【9】数据一致性验证：')
# 净金额一致性
r1 = pd.read_sql("SELECT SUM(净金额) FROM 成果表", conn).iloc[0, 0]
r2 = pd.read_sql("SELECT SUM(净金额) FROM 销售流水", conn).iloc[0, 0]
print(f'  成果表净金额合计: {r1:.2f} | 销售流水净金额合计: {r2:.2f} | {"一致" if abs(r1-r2)<0.01 else "不一致"}')

# 数量一致性
r1 = pd.read_sql("SELECT SUM(数量) FROM 成果表", conn).iloc[0, 0]
r2 = pd.read_sql("SELECT SUM(数量) FROM 销售流水", conn).iloc[0, 0]
print(f'  成果表数量合计: {r1:.0f} | 销售流水数量合计: {r2:.0f} | {"一致" if abs(r1-r2)<0.01 else "不一致"}')

conn.close()
print('\n验证完成。')
