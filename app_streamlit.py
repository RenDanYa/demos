import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title='成果表生成', page_icon='📊', layout='wide')

st.title('📊 成果表生成工具')
st.caption('上传Excel → 自动处理 → 预览 & 下载')

# ========== 文件来源 ==========
DEFAULT_FILE = r'c:\Users\godisgirl\.trae-cn\attachments\6a8bfd85e15d64a332569168\72b3f34c-a8ed-45ba-9b0d-418e8cf14243_测试.xlsx'
uploaded = st.file_uploader('拖入Excel文件（测试.xlsx）', type=['xlsx'])

SRC = uploaded if uploaded is not None else DEFAULT_FILE

if SRC is not None:
    with st.spinner('读取文件中...'):
        xls = pd.ExcelFile(SRC)
        sheets = xls.sheet_names
    st.success(f'已识别 {len(sheets)} 个工作表：{" / ".join(sheets)}')

    with st.spinner('[1/6] 读取商品描述、division...'):
        master = pd.read_excel(SRC, sheet_name='商品描述、division', header=0)
        master = master[['Article', 'Article Name', 'Division']].dropna(subset=['Article'])
        master = master.drop_duplicates(subset='Article', keep='first')
        master_dict = master.set_index('Article')[['Article Name', 'Division']].to_dict('index')
    st.info(f'商品主数据：{len(master_dict)} 条')

    with st.spinner('[2/6] 读取净金额、数量...'):
        sales = pd.read_excel(SRC, sheet_name='净金额、数量', header=0)
        sales = sales[sales['商品编号'].astype(str).str.startswith('GD')]
        sales_agg = sales.groupby('商品编号').agg(
            净金额=('净金额', 'sum'),
            数量=('数量', 'sum')
        ).reset_index()
        sales_agg['净金额'] = sales_agg['净金额'].abs()
        sales_agg['数量'] = sales_agg['数量'].abs()
        sales_agg = sales_agg.rename(columns={'商品编号': '物料编号'})
    st.info(f'销售汇总：{len(sales_agg)} 条')

    with st.spinner('[3/6] 读取出样...'):
        cy = pd.read_excel(SRC, sheet_name='出样', header=0)
        cy['出样'] = cy['收据号'].astype(str) + '|' + cy['数量'].astype(str)
        cy_dict = cy.set_index('物料编号')['出样'].to_dict()
    st.info(f'出样记录：{len(cy_dict)} 条')

    with st.spinner('[4/6] 读取库存表（13万行，请稍候）...'):
        inv_raw = pd.read_excel(SRC, sheet_name='库存', header=None)
        h1_idx = inv_raw.index[inv_raw.eq('物料编号').any(axis=1)][0]
        h2_idx = h1_idx + 1
        inv_data = inv_raw.iloc[h2_idx + 1:]
        inv = inv_data.iloc[:, [2, 11, 19]].copy()
        inv.columns = ['物料编号', '尺寸', '库存量']
        inv = inv[inv['物料编号'].astype(str).str.startswith('GD')].reset_index(drop=True)
        inv['库存量'] = pd.to_numeric(inv['库存量'], errors='coerce')
    st.info(f'库存数据：{len(inv)} 行')

    with st.spinner('提取当日库存 & 库存尺码...'):
        inv_stock = inv.dropna(subset=['库存量'])
        stock_dict = inv_stock.groupby('物料编号')['库存量'].sum().to_dict()
        inv_stock = inv_stock.copy()
        inv_stock['库存尺码'] = inv_stock['尺寸'].astype(str) + '|' + inv_stock['库存量'].astype(int).astype(str)
        size_dict = inv_stock.groupby('物料编号')['库存尺码'].apply(lambda s: '、'.join(s)).to_dict()
    st.info(f'有库存物料：{len(stock_dict)} 个')

    with st.spinner('[5/6] 汇总成果表...'):
        result = sales_agg.copy()
        result['商品描述'] = result['物料编号'].map(lambda x: master_dict.get(x, {}).get('Article Name', ''))
        result['Division'] = result['物料编号'].map(lambda x: master_dict.get(x, {}).get('Division', ''))
        result['出样'] = result['物料编号'].map(cy_dict)
        result['当日库存'] = result['物料编号'].map(stock_dict)
        result['库存尺码'] = result['物料编号'].map(size_dict)
        result = result[['商品描述', 'Division', '物料编号', '净金额', '数量', '当日库存', '出样', '库存尺码']]

    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('物料总数', len(result))
    col2.metric('有出样', result['出样'].notna().sum())
    col3.metric('有当日库存', result['当日库存'].notna().sum())
    col4.metric('有库存尺码', result['库存尺码'].notna().sum())

    st.divider()
    st.subheader('成果表预览')
    st.dataframe(result, use_container_width=True, height=400)

    st.divider()
    st.subheader('可视化图表')
    tab1, tab2 = st.tabs(['净金额TOP10', '数量分布'])
    with tab1:
        top10 = result.nlargest(10, '净金额')[['物料编号', '商品描述', '净金额']]
        st.bar_chart(top10.set_index('物料编号')['净金额'])
        st.dataframe(top10, use_container_width=True)
    with tab2:
        st.bar_chart(result.set_index('物料编号')['数量'].head(20))

    st.divider()
    st.subheader('下载文件')
    col_dl1, col_dl2 = st.columns(2)

    with col_dl1:
        buf1 = io.BytesIO()
        result.to_excel(buf1, sheet_name='成果', index=False)
        buf1.seek(0)
        st.download_button(
            '📥 下载成果表',
            buf1,
            file_name='成果_输出.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    with col_dl2:
        buf2 = io.BytesIO()
        inv[['物料编号', '尺寸', '库存量']].to_excel(buf2, sheet_name='库存_明细', index=False)
        buf2.seek(0)
        st.download_button(
            '📥 下载库存明细',
            buf2,
            file_name='库存_明细.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
