import io
import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime

# ========== 全局配置 ==========
st.set_page_config(page_title='业务看板', page_icon='📊', layout='wide')

DB_PATH = '业务数据库.db'

@st.cache_data(ttl=300)
def query_db(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()
    return df

@st.cache_data(ttl=300)
def get_table_names():
    conn = sqlite3.connect(DB_PATH)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
    except:
        tables = []
    finally:
        conn.close()
    return tables

@st.cache_data(ttl=300)
def get_date_list():
    try:
        df = query_db("SELECT DISTINCT 导入日期 FROM 成果表 ORDER BY 导入日期 DESC")
        return df['导入日期'].tolist()
    except:
        return []

def db_exists():
    return os.path.exists(DB_PATH)

# ========== 侧边栏 ==========
with st.sidebar:
    st.title('📊 业务看板')
    st.divider()
    page = st.radio('页面导航', [
        '📊 销售概览',
        '📈 趋势分析',
        '📦 库存看板',
        '📋 明细数据',
        '📥 数据导入'
    ])
    st.divider()

    if db_exists():
        dates = get_date_list()
        if dates:
            st.subheader('筛选条件')
            selected_date = st.selectbox('数据日期', ['全部'] + dates)
            divisions_raw = query_db("SELECT DISTINCT Division FROM 成果表 WHERE Division IS NOT NULL")
            divisions = divisions_raw['Division'].tolist()
            selected_div = st.selectbox('Division', ['全部'] + divisions)
        else:
            st.warning('数据库为空，请先导入数据')
    else:
        st.warning('数据库不存在，请先在"数据导入"页上传Excel')

    st.divider()
    st.caption(f'更新时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}')

# ========== 辅助函数 ==========
def filter_df(df, date_col='导入日期', div_col='Division'):
    if 'selected_date' in globals() and selected_date != '全部':
        df = df[df[date_col] == selected_date]
    if 'selected_div' in globals() and selected_div != '全部':
        df = df[df[div_col] == selected_div]
    return df

# ========== 页面1：销售概览 ==========
if page == '📊 销售概览':
    st.header('📊 销售概览')

    if not db_exists() or not get_date_list():
        st.warning('暂无数据，请先到"数据导入"页上传Excel。')
    else:
        df = query_db("SELECT * FROM 成果表")
        df = filter_df(df)

        total_amount = df['净金额'].sum()
        total_qty = df['数量'].sum()
        sku_count = len(df)
        avg_price = total_amount / total_qty if total_qty > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric('总销售额', f'¥{total_amount:,.0f}')
        c2.metric('总数量', f'{total_qty:,.0f}')
        c3.metric('物料数', f'{sku_count}')
        c4.metric('均价', f'¥{avg_price:,.0f}')

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader('品类销售占比')
            div_summary = df.groupby('Division')['净金额'].sum().reset_index()
            fig = px.pie(div_summary, values='净金额', names='Division',
                         hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(margin=dict(t=30, b=0), height=350)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader('TOP10 物料销售额')
            top10 = df.nlargest(10, '净金额')[['物料编号', '商品描述', '净金额']]
            fig = px.bar(top10, x='净金额', y='物料编号', orientation='h',
                         text='净金额', color='净金额',
                         color_continuous_scale='Blues')
            fig.update_traces(texttemplate='¥%{text:,.0f}', textposition='outside')
            fig.update_layout(yaxis={'categoryorder': 'total ascending'},
                              margin=dict(t=30, b=0), height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        col3, col4 = st.columns(2)
        with col3:
            st.subheader('Division 销售对比')
            fig = px.bar(div_summary, x='Division', y='净金额',
                         color='Division', text='净金额')
            fig.update_traces(texttemplate='¥%{text:,.0f}', textposition='outside')
            fig.update_layout(showlegend=False, margin=dict(t=30, b=0), height=350)
            st.plotly_chart(fig, use_container_width=True)

        with col4:
            st.subheader('销售数量分布')
            fig = px.histogram(df, x='数量', nbins=20, color='Division')
            fig.update_layout(showlegend=False, margin=dict(t=30, b=0), height=350)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        with st.expander('查看明细数据'):
            st.dataframe(df[['商品描述', 'Division', '物料编号', '净金额', '数量',
                             '当日库存', '出样', '库存尺码']].sort_values('净金额', ascending=False),
                         use_container_width=True, height=400)

# ========== 页面2：趋势分析 ==========
elif page == '📈 趋势分析':
    st.header('📈 趋势分析')

    if not db_exists() or not get_date_list():
        st.warning('暂无数据，需要多天导入后才能看趋势。')
    else:
        metric = st.radio('分析指标', ['净金额', '数量'], horizontal=True)
        df_trend = query_db(f'''
            SELECT 导入日期, SUM({metric}) AS 日总值
            FROM 成果表 GROUP BY 导入日期 ORDER BY 导入日期
        ''')

        if len(df_trend) < 2:
            st.info('目前只有1天的数据，多天导入后可查看趋势。当前展示单日数据。')

        tab1, tab2, tab3 = st.tabs(['📈 折线趋势', '📊 柱状对比', '📋 数据明细'])

        with tab1:
            fig = px.line(df_trend, x='导入日期', y='日总值',
                          title=f'每日{metric}趋势', markers=True,
                          line_shape='linear')
            fig.update_traces(line_width=3, marker_size=8)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            fig = px.bar(df_trend, x='导入日期', y='日总值',
                         text='日总值', title=f'每日{metric}对比')
            fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

        with tab3:
            df_trend['日总值'] = df_trend['日总值'].round(2)
            if len(df_trend) >= 2:
                df_trend['环比变化'] = df_trend['日总值'].pct_change()
                df_trend['环比变化'] = df_trend['环比变化'].apply(
                    lambda x: f'{x:+.1%}' if pd.notna(x) else '-'
                )
            st.dataframe(df_trend, use_container_width=True, hide_index=True)

# ========== 页面3：库存看板 ==========
elif page == '📦 库存看板':
    st.header('📦 库存看板')

    if not db_exists() or not get_date_list():
        st.warning('暂无数据，请先导入。')
    else:
        df_inv = query_db("SELECT * FROM 库存明细")
        df_inv = filter_df(df_inv)
        df_inv = df_inv.dropna(subset=['库存量'])

        total_sku = len(df_inv['物料编号'].unique())
        in_stock = len(df_inv[df_inv['库存量'] > 0]['物料编号'].unique())
        out_stock = total_sku - in_stock
        total_qty = df_inv['库存量'].sum()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric('总SKU数', f'{total_sku:,}')
        c2.metric('有库存', f'{in_stock:,}')
        c3.metric('无库存', f'{out_stock:,}')
        c4.metric('总库存量', f'{total_qty:,.0f}')

        st.divider()

        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader('尺码分布')
            size_dist = df_inv.groupby('尺寸')['库存量'].sum().reset_index()
            size_dist = size_dist.sort_values('库存量', ascending=False).head(20)
            fig = px.bar(size_dist, x='尺寸', y='库存量', color='库存量',
                         color_continuous_scale='Viridis')
            fig.update_layout(height=350, showlegend=False, margin=dict(t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader('库存量分布')
            fig = px.histogram(df_inv, x='库存量', nbins=15,
                               title='库存量频次分布')
            fig.update_layout(height=350, showlegend=False, margin=dict(t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.subheader('库存明细预览')
        st.dataframe(df_inv[['物料编号', '尺寸', '库存量']].head(500),
                     use_container_width=True, height=300)

# ========== 页面4：明细数据 ==========
elif page == '📋 明细数据':
    st.header('📋 明细数据')

    if not db_exists() or not get_table_names():
        st.warning('暂无数据，请先导入。')
    else:
        tables = get_table_names()
        table_name = st.selectbox('选择数据表', tables)

        df_detail = query_db(f"SELECT * FROM {table_name}")
        st.caption(f'共 {len(df_detail):,} 行')

        search_col = st.selectbox('搜索列', [''] + df_detail.columns.tolist())
        search_val = st.text_input('搜索内容（模糊匹配）')

        if search_col and search_val:
            mask = df_detail[search_col].astype(str).str.contains(search_val, case=False, na=False)
            df_detail = df_detail[mask]
            st.caption(f'筛选后 {len(df_detail):,} 行')

        st.dataframe(df_detail, use_container_width=True, height=500)

        st.divider()
        buf = io.BytesIO()
        df_detail.to_excel(buf, index=False, sheet_name=table_name)
        buf.seek(0)
        st.download_button('📥 下载当前数据', buf, file_name=f'{table_name}.xlsx',
                           mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ========== 页面5：数据导入 ==========
elif page == '📥 数据导入':
    st.header('📥 数据导入')

    st.write('上传Excel文件，自动清洗并导入数据库。')

    uploaded = st.file_uploader('拖入Excel文件', type=['xlsx'])

    if uploaded is not None:
        st.success(f'已上传：{uploaded.name}')

        if st.button('🚀 开始导入', type='primary'):
            progress = st.progress(0, text='读取文件中...')
            today = str(date.today())

            try:
                progress.progress(10, text='[1/6] 读取商品描述、division...')
                master = pd.read_excel(uploaded, sheet_name='商品描述、division', header=0)
                master = master[['Article', 'Article Name', 'Division']].dropna(subset=['Article'])
                master = master.drop_duplicates(subset='Article', keep='first')
                master['导入日期'] = today
                st.info(f'商品主数据：{len(master)} 条')

                progress.progress(25, text='[2/6] 读取净金额、数量...')
                sales = pd.read_excel(uploaded, sheet_name='净金额、数量', header=0)
                sales = sales[sales['商品编号'].astype(str).str.startswith('GD')]
                sales['净金额'] = sales['净金额'].abs()
                sales['数量'] = sales['数量'].abs()
                sales['导入日期'] = today
                st.info(f'销售流水：{len(sales)} 条')

                progress.progress(40, text='[3/6] 读取出样记录...')
                cy = pd.read_excel(uploaded, sheet_name='出样', header=0)
                cy['导入日期'] = today
                st.info(f'出样记录：{len(cy)} 条')

                progress.progress(55, text='[4/6] 读取库存表（13万行，请稍候）...')
                inv_raw = pd.read_excel(uploaded, sheet_name='库存', header=None)
                h1_idx = inv_raw.index[inv_raw.eq('物料编号').any(axis=1)][0]
                h2_idx = h1_idx + 1
                inv_data = inv_raw.iloc[h2_idx + 1:]
                inv = inv_data.iloc[:, [2, 11, 19]].copy()
                inv.columns = ['物料编号', '尺寸', '库存量']
                inv = inv[inv['物料编号'].astype(str).str.startswith('GD')].reset_index(drop=True)
                inv['库存量'] = pd.to_numeric(inv['库存量'], errors='coerce')
                inv['导入日期'] = today
                st.info(f'库存数据：{len(inv)} 行')

                progress.progress(70, text='[5/6] 汇总成果表...')
                sales_agg = sales.groupby('商品编号').agg(
                    净金额=('净金额', 'sum'), 数量=('数量', 'sum')
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
                result = result[['商品描述', 'Division', '物料编号', '净金额', '数量',
                                 '当日库存', '出样', '库存尺码']]
                result['导入日期'] = today
                st.info(f'成果表：{len(result)} 行')

                progress.progress(85, text='[6/6] 导入数据库...')
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
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
                for table in ['商品主数据', '销售流水', '出样记录', '库存明细', '成果表']:
                    cur.execute(f"DELETE FROM {table} WHERE 导入日期 = ?", (today,))
                master_db = master[['Article', 'Article Name', 'Division', '导入日期']].copy()
                master_db.columns = ['物料编号', '商品描述', 'Division', '导入日期']
                master_db.to_sql('商品主数据', conn, if_exists='append', index=False)
                sales[['商品编号', '净金额', '数量', '导入日期']].to_sql('销售流水', conn, if_exists='append', index=False)
                cy[['物料编号', '收据号', '数量', '导入日期']].to_sql('出样记录', conn, if_exists='append', index=False)
                inv[['物料编号', '尺寸', '库存量', '导入日期']].to_sql('库存明细', conn, if_exists='append', index=False)
                result.to_sql('成果表', conn, if_exists='append', index=False)
                conn.commit()
                conn.close()

                st.cache_data.clear()
                progress.progress(100, text='导入完成！')
                st.success(f'''
                ✅ 导入成功！

                - 商品主数据：{len(master)} 条
                - 销售流水：{len(sales)} 条
                - 出样记录：{len(cy)} 条
                - 库存明细：{len(inv)} 行
                - 成果表：{len(result)} 行
                - 导入日期：{today}
                ''')

                col1, col2 = st.columns(2)
                with col1:
                    buf1 = io.BytesIO()
                    result.drop(columns=['导入日期']).to_excel(buf1, sheet_name='成果', index=False)
                    buf1.seek(0)
                    st.download_button('📥 下载成果表', buf1, file_name='成果_输出.xlsx')
                with col2:
                    buf2 = io.BytesIO()
                    inv[['物料编号', '尺寸', '库存量']].to_excel(buf2, sheet_name='库存明细', index=False)
                    buf2.seek(0)
                    st.download_button('📥 下载库存明细', buf2, file_name='库存_明细.xlsx')

            except Exception as e:
                st.error(f'导入失败：{e}')
