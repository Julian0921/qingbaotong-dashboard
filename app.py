#!/usr/bin/env python3
"""情报通 2024-2025 数据看板 V10 - 从 GitHub Release 自动下载数据"""
import os, sys, tempfile, shutil, gzip, requests, json as _json

# ========== GitHub Release 数据加载 ==========
_DATA_DIR = os.path.join(tempfile.gettempdir(), "qingbaotong_data")
os.makedirs(_DATA_DIR, exist_ok=True)
_PKL_2025 = os.path.join(_DATA_DIR, "qingbaotong_2025_full.pkl")
_PKL_2024 = os.path.join(_DATA_DIR, "qingbaotong_2024_full.pkl")

_RELEASE_BASE = "https://github.com/Julian0921/qingbaotong-dashboard/releases/download/v1.0"
_DATA_FILES = {
    "qingbaotong_2025_full.pkl.gz": _PKL_2025,
    "qingbaotong_2024_full.pkl.gz": _PKL_2024,
}

def _download_file(url, dest, chunk=1024*1024*10):
    """下载文件到dest，显示进度"""
    r = requests.get(url, stream=True, timeout=600)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    downloaded = 0
    with open(dest, "wb") as f:
        for c in r.iter_content(chunk_size=chunk):
            if c:
                f.write(c)
                downloaded += len(c)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r  下载进度: {pct}% ({downloaded//1024//1024}/{total//1024//1024}MB)", end="", flush=True)
    print()
    return dest

def _gunzip(src, dest):
    """解压gz文件到dest"""
    with gzip.open(src, "rb") as fin:
        with open(dest, "wb") as fout:
            shutil.copyfileobj(fin, fout)

def _ensure_data():
    """确保pkl数据文件存在，不存在则从GitHub Release下载gz并解压"""
    missing = []
    for gz_name, pkl_path in _DATA_FILES.items():
        if not os.path.exists(pkl_path):
            missing.append(gz_name)

    if not missing:
        print("✅ 数据文件已存在，直接加载")
        return

    print(f"📡 数据文件缺失，从 GitHub Release 下载: {missing}")
    for gz_name in missing:
        pkl_path = _DATA_FILES[gz_name]
        gz_path = gz_name + ".tmp"
        url = f"{_RELEASE_BASE}/{gz_name}"
        print(f"📥 正在下载 {gz_name}...")
        _download_file(url, gz_path)
        print(f"📦 正在解压...")
        _gunzip(gz_path, pkl_path)
        os.remove(gz_path)
        size_mb = os.path.getsize(pkl_path) / 1e6
        print(f"✅ {gz_name} 解压完成 ({size_mb:.1f}MB)")

# ========== 主程序 ==========
_ensure_data()

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, html, dcc, callback, Output, Input, State
from dash.dash_table import DataTable
import dash

print("加载数据...")
df25 = pd.read_pickle(_PKL_2025)
df24 = pd.read_pickle(_PKL_2024)

# 只保留需要的列（节省内存）
keep_cols = ['平台', '月', 'Lv1类目名称(逐月固定)', 'Lv2类目名称(逐月固定)', 
             '宝贝ID', '宝贝名称', '宝贝品牌(bid)', '宝贝店铺名称', '销量', '销售额', '成交均价']
df25 = df25[[c for c in keep_cols if c in df25.columns]]
df24 = df24[[c for c in keep_cols if c in df24.columns]]

# 标记年份
df25["年份"] = 2025; df24["年份"] = 2024
df = pd.concat([df24, df25], ignore_index=True)
del df24, df25

# 处理列 - 使用category加速groupby
df["品牌"] = df["宝贝品牌(bid)"].fillna("未知品牌").astype("category")
df["月份"] = df["月"].astype(str).astype("category")
df["年份"] = df["年份"].astype("uint16")
df["成交均价"] = pd.to_numeric(df["成交均价"], errors="coerce")
df["平台"] = df["平台"].astype("category")
df["Lv1类目名称(逐月固定)"] = df["Lv1类目名称(逐月固定)"].astype("category")
df["Lv2类目名称(逐月固定)"] = df["Lv2类目名称(逐月固定)"].astype("category")
df["宝贝店铺名称"] = df["宝贝店铺名称"].astype("category")
df["宝贝ID"] = df["宝贝ID"].astype("int64")
print(f"✅ 合计: {len(df):,} 行")

CAT1_TO_CAT2 = {}
for c1 in df["Lv1类目名称(逐月固定)"].unique():
    CAT1_TO_CAT2[c1] = sorted(df[df["Lv1类目名称(逐月固定)"]==c1]["Lv2类目名称(逐月固定)"].unique().tolist())

ALL_CAT1 = sorted(df["Lv1类目名称(逐月固定)"].unique())
ALL_CAT2 = sorted(df["Lv2类目名称(逐月固定)"].unique())
ALL_BRANDS = df["品牌"].value_counts().head(80).index.tolist()
ALL_PLATFORMS = sorted(df["平台"].unique().tolist())

# 预计算选项（按年份）
PRE_MONTHS_ALL = sorted(df["月份"].unique())
PRE_MONTHS_24 = sorted(df[df["年份"]==2024]["月份"].unique())
PRE_MONTHS_25 = sorted(df[df["年份"]==2025]["月份"].unique())
PRE_BRANDS_ALL = df.groupby("品牌")["销售额"].sum().sort_values(ascending=False).head(200).index.tolist()
PRE_BRANDS_24 = df[df["年份"]==2024].groupby("品牌")["销售额"].sum().sort_values(ascending=False).head(200).index.tolist()
PRE_BRANDS_25 = df[df["年份"]==2025].groupby("品牌")["销售额"].sum().sort_values(ascending=False).head(200).index.tolist()
MONTH_OPT = [{"label":"0-50元","value":"0-50"},{"label":"50-100元","value":"50-100"},{"label":"100-200元","value":"100-200"},{"label":"200-500元","value":"200-500"},{"label":"500-1000元","value":"500-1000"},{"label":"1000+元","value":"1000+"}]
print("✅ 预计算完成")

app = Dash(__name__)
app.title = "情报通 2024-2025 V10"
PRICE_BINS = {"0-50":(0,50),"50-100":(50,100),"100-200":(100,200),"200-500":(200,500),"500-1000":(500,1000),"1000+":(1000,999999)}

def kpi(title, val, unit="", color="#3b82f6"):
    return html.Div([
        html.Div(title, style={"color":"#64748b","fontSize":"11px","marginBottom":"3px"}),
        html.Div([
            html.Span(f"{val:,.0f}" if isinstance(val,(int,float)) else f"{val:,}", style={"fontSize":"22px","fontWeight":"bold","color":color}),
            html.Span(f" {unit}" if unit else "", style={"fontSize":"12px","color":"#64748b"})
        ])
    ], style={"background":"#fff","padding":"14px 10px","borderRadius":"10px","textAlign":"center"})

def filter_df(dff, months, cat1, cat2, brands, platforms, prices):
    if months: 
        months_str = [str(m) for m in months]
        dff = dff[dff["月份"].isin(months_str)]
    if brands: dff = dff[dff["品牌"].isin(brands)]
    if platforms: dff = dff[dff["平台"].isin(platforms)]
    if cat1: dff = dff[dff["Lv1类目名称(逐月固定)"].isin(cat1)]
    if cat2: dff = dff[dff["Lv2类目名称(逐月固定)"].isin(cat2)]
    if prices:
        mask = pd.Series(False, index=dff.index)
        for p in prices:
            if p in PRICE_BINS:
                lo, hi = PRICE_BINS[p]
                mask |= (dff["成交均价"]>=lo) & (dff["成交均价"]<hi)
        dff = dff[mask]
    return dff

def make_table(data, cols, height=320):
    style_data_conditional = [{"if":{"row_index":"odd"},"background":"#f8fafc"}]
    if "YOY(%)" in cols:
        style_data_conditional.extend([
            {"if":{"column_id":"YOY(%)","filter_query":"{YOY(%)} > 0"},"color":"#ef4444","fontWeight":"bold"},
            {"if":{"column_id":"YOY(%)","filter_query":"{YOY(%)} < 0"},"color":"#10b981","fontWeight":"bold"},
        ])
    return DataTable(
        data=data.to_dict("records"),
        columns=[{"name":c,"id":c} for c in cols],
        page_size=20, page_action="native",
        style_cell={"padding":"5px","fontSize":"11px","textAlign":"center"},
        style_header={"background":"#f1f5f9","fontWeight":"bold","fontSize":"12px","position":"sticky","top":"0","zIndex":"10"},
        style_data_conditional=style_data_conditional,
        style_table={"maxHeight":f"{height}px","overflowY":"auto","overflowX":"auto"}
    )

brand_cnt = df["品牌"].nunique()
row_cnt = len(df)
app.layout = html.Div([
    html.Div([
        html.H1("📊 情报通 2024-2025 数据看板 V10", style={"color":"#1e293b","margin":"0","fontSize":"24px"}),
        html.Div([html.Span(f"📦 {row_cnt:,} 条 | 🏢 {brand_cnt:,} 品牌")], style={"color":"#64748b","margin":"6px 0 0 0","fontSize":"12px"})
    ], style={"textAlign":"center","padding":"18px","background":"#fff","borderRadius":"12px","marginBottom":"12px"}),
    html.Div([
        dcc.Location(id="url-trigger"),
        html.Div([html.Div("📆 年份"), dcc.Dropdown(id="dd-year", options=[{"label":"2024+2025","value":"all"},{"label":"2024年","value":"2024"},{"label":"2025年","value":"2025"}], value="all", clearable=False)], style={"width":"110px"}),
        html.Div([html.Div("📅 月份"), dcc.Dropdown(id="dd-month", multi=True, placeholder="全部")], style={"width":"120px"}),
        html.Div([html.Div("🏷️ 一级类目", style={"color":"#8b5cf6"}), dcc.Dropdown(id="dd-cat1", multi=True, placeholder="选择")], style={"width":"150px"}),
        html.Div([html.Div("🏷️ 二级类目", style={"color":"#10b981"}), dcc.Dropdown(id="dd-cat2", multi=True, placeholder="选择")], style={"width":"150px"}),
        html.Div([html.Div("🏢 品牌"), dcc.Dropdown(id="dd-brand", multi=True, placeholder="全部")], style={"width":"170px"}),
        html.Div([html.Div("🏪 平台"), dcc.Dropdown(id="dd-platform", multi=True, placeholder="全部")], style={"width":"140px"}),
        html.Div([html.Div("💰 价格", style={"color":"#f59e0b"}), dcc.Dropdown(id="dd-price", multi=True, placeholder="全部")], style={"width":"120px"}),
        html.Div([html.Button("✅ 应用", id="btn-apply", n_clicks=0, style={"background":"#3b82f6","color":"white","border":"none","padding":"10px 16px","borderRadius":"8px","cursor":"pointer","fontWeight":"bold"}), html.Button("🔄 重置", id="btn-reset", n_clicks=0, style={"background":"#e2e8f0","border":"none","padding":"10px 14px","borderRadius":"8px","cursor":"pointer","marginLeft":"6px"})], style={"display":"flex","alignItems":"flexEnd"}),
    ], style={"background":"#fff","padding":"14px","borderRadius":"12px","display":"flex","flexWrap":"wrap","alignItems":"flexEnd","gap":"10px","marginBottom":"12px"}),
    html.Div(id="filter-status", style={"background":"#f0f9ff","padding":"8px 12px","borderRadius":"8px","marginBottom":"12px","fontSize":"12px","color":"#3b82f6"}),
    html.Div([
        html.Div([html.Span("📊 展示："), dcc.Checklist(id="data-mode", options=[{"label":" 绝对值","value":"abs"},{"label":" 百分比","value":"pct"}], value=["abs"], inline=True)], style={"marginRight":"20px"}),
        html.Div([html.Span("📈 同比："), dcc.Checklist(id="yoy-toggle", options=[{"label":" 开启2024对比","value":"yoy"}], value=[], inline=True)])
    ], style={"background":"#fff","padding":"10px","borderRadius":"8px","marginBottom":"12px","display":"flex"}),
    html.Div(id="kpi-row", style={"display":"grid","gridTemplateColumns":"repeat(6,1fr)","gap":"10px","marginBottom":"12px"}),
    html.Div([html.Div([dcc.Graph(id="g-trend")], style={"flex":"1","background":"#fff","padding":"12px","borderRadius":"12px","marginRight":"10px"}), html.Div([dcc.Graph(id="g-cat1")], style={"flex":"1","background":"#fff","padding":"12px","borderRadius":"12px"})], style={"display":"flex","marginBottom":"10px"}),
    html.Div([html.Div([dcc.Graph(id="g-cat2")], style={"flex":"1","background":"#fff","padding":"12px","borderRadius":"12px","marginRight":"10px"}), html.Div([dcc.Graph(id="g-price")], style={"flex":"1","background":"#fff","padding":"12px","borderRadius":"12px"})], style={"display":"flex","marginBottom":"10px"}),
    html.Div([html.Div([dcc.Graph(id="g-platform")], style={"flex":"1","background":"#fff","padding":"12px","borderRadius":"12px","marginRight":"10px"}), html.Div([dcc.Graph(id="g-brand")], style={"flex":"1","background":"#fff","padding":"12px","borderRadius":"12px"})], style={"display":"flex","marginBottom":"12px"}),
    html.Div([
        html.Div("🏪 店铺排名 Top100（表格可翻页）", style={"fontWeight":"bold","fontSize":"13px","marginBottom":"10px","color":"#ef4444"}), 
        html.Div(id="store-table-area", style={"maxHeight":"380px","overflowY":"auto"})
    ], style={"background":"#fff","padding":"15px","borderRadius":"12px","marginBottom":"12px"}),
    html.Div(id="drill-section", style={"display":"none"}, children=[
        html.Div([html.Div(id="drill-title", style={"fontSize":"16px","fontWeight":"bold"}), html.Button("❌ 关闭", id="btn-close-drill", n_clicks=0, style={"background":"#fee2e2","color":"#ef4444","border":"none","padding":"8px 16px","borderRadius":"8px","cursor":"pointer","marginLeft":"auto"})], style={"display":"flex","marginBottom":"12px"}),
        html.Div([html.Div([dcc.Graph(id="d-monthly")], style={"flex":"1","background":"#fff","padding":"12px","borderRadius":"12px","marginRight":"8px"}), html.Div([dcc.Graph(id="d-price")], style={"flex":"1","background":"#fff","padding":"12px","borderRadius":"12px"})], style={"display":"flex","marginBottom":"8px"}),
        html.Div([html.Div([html.Div("🏪 店铺 Top100", style={"fontWeight":"bold","marginBottom":"8px","color":"#ef4444"}), html.Div(id="d-store-table")], style={"flex":"1","background":"#fff","padding":"12px","borderRadius":"12px","marginRight":"8px"}), html.Div([html.Div("🛍️ 商品 Top100", style={"fontWeight":"bold","marginBottom":"8px","color":"#f59e0b"}), html.Div(id="d-product-table")], style={"flex":"1","background":"#fff","padding":"12px","borderRadius":"12px"})], style={"display":"flex"}),
    ]),
], style={"background":"#f8fafc","padding":"15px","minHeight":"100vh"})

@app.callback([Output("dd-month","value"), Output("dd-cat1","value"), Output("dd-cat2","value"), Output("dd-brand","value"), Output("dd-platform","value"), Output("dd-price","value")], [Input("btn-reset","n_clicks")])
def reset_filters(n):
    return [None,None,None,None,None,None]

@app.callback([Output("dd-month","options"), Output("dd-cat1","options"), Output("dd-cat2","options"), Output("dd-brand","options"), Output("dd-platform","options"), Output("dd-price","options")], [Input("dd-year","value"), Input("url-trigger","pathname")])
def init_dropdowns(year, _):
    if not year: year = "all"
    if year == "2024":
        months = PRE_MONTHS_24
        brands = PRE_BRANDS_24
    elif year == "2025":
        months = PRE_MONTHS_25
        brands = PRE_BRANDS_25
    else:
        months = PRE_MONTHS_ALL
        brands = PRE_BRANDS_ALL
    return ([{"label":m,"value":m} for m in months], [{"label":c,"value":c} for c in ALL_CAT1], [{"label":c,"value":c} for c in ALL_CAT2], [{"label":b,"value":b} for b in brands], [{"label":p,"value":p} for p in ALL_PLATFORMS], MONTH_OPT)

@app.callback([Output("dd-cat2","options"), Output("dd-cat2","value")], [Input("dd-cat1","value")], [State("dd-cat2","value")])
def cat1_to_cat2(cat1_sel, cur_cat2):
    if not cat1_sel: return [{"label":c,"value":c} for c in ALL_CAT2], None
    cat2_set = set()
    for c in cat1_sel:
        if c in CAT1_TO_CAT2: cat2_set.update(CAT1_TO_CAT2[c])
    opts = [{"label":c,"value":c} for c in sorted(cat2_set)]
    valid = {o["value"] for o in opts}
    filt = [c for c in (cur_cat2 or []) if c in valid] or None
    return opts, filt

@app.callback([Output("kpi-row","children"), Output("g-trend","figure"), Output("g-cat1","figure"), Output("g-cat2","figure"), Output("g-price","figure"), Output("g-platform","figure"), Output("g-brand","figure"), Output("store-table-area","children"), Output("filter-status","children"), Output("drill-section","style")], [Input("btn-apply","n_clicks"), Input("btn-close-drill","n_clicks"), Input("data-mode","value"), Input("yoy-toggle","value"), Input("dd-year","value"), Input("dd-month","value")], [State("dd-cat1","value"), State("dd-cat2","value"), State("dd-brand","value"), State("dd-platform","value"), State("dd-price","value")])
def update_board(apply_n, close_n, modes, yoy_val, year, months, cat1, cat2, brands, platforms, prices):
    ctx = dash.callback_context
    t = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""
    if t == "btn-close-drill": return [dash.no_update]*9 + [{"display":"none"}]
    
    if year and year != "all":
        year_filter = df[df["年份"]==int(year)]
    else:
        year_filter = df
    
    has_filter = (apply_n > 0) or (months and len(months) > 0) or (cat1 and len(cat1) > 0) or (cat2 and len(cat2) > 0) or (brands and len(brands) > 0) or (platforms and len(platforms) > 0) or (prices and len(prices) > 0)
    
    if not has_filter:
        dff = year_filter; status = "📌 全部数据 | 点击图表下钻"
    else:
        dff = filter_df(year_filter, months, cat1, cat2, brands, platforms, prices)
        parts = []
        if months: parts.append(f"月份{len(months)}个")
        if cat1: parts.append(f"类目{len(cat1)}个")
        if cat2: parts.append(f"子类{len(cat2)}个")
        if brands: parts.append(f"品牌{len(brands)}个")
        status = f"📌 {', '.join(parts) if parts else '全部'} | {len(dff):,} 条"
    
    ts, tq = dff["销售额"].sum(), dff["销量"].sum()
    ap = dff["成交均价"].mean() if len(dff)>0 else 0
    show_yoy = "yoy" in yoy_val
    
    months_2024 = None
    dff_2024 = None
    if show_yoy and year != "2024":
        months_2024 = []
        for m in (months or []):
            m_str = str(m)
            months_2024.append(int(m_str.replace("2025", "2024")) if "2025" in m_str else int(m_str))
        dff_2024 = filter_df(df[df["年份"]==2024], months_2024, cat1, cat2, brands, platforms, prices)
    
    if show_yoy and year != "2024" and dff_2024 is not None and len(dff_2024) > 0:
        ts_24, tq_24 = dff_2024["销售额"].sum(), dff_2024["销量"].sum()
        ap_24 = dff_2024["成交均价"].mean() if len(dff_2024)>0 else 0
        yoy_ts = ((ts/ts_24 - 1) * 100) if ts_24 > 0 else 0
        yoy_tq = ((tq/tq_24 - 1) * 100) if tq_24 > 0 else 0
        yoy_ap = ((ap/ap_24 - 1) * 100) if ap_24 > 0 else 0
        
        def kpi_yoy(title, val25, val24, yoy, unit="", color="#3b82f6"):
            yoy_color = "#10b981" if yoy >= 0 else "#ef4444"
            yoy_sign = "+" if yoy >= 0 else ""
            return html.Div([
                html.Div(title, style={"color":"#64748b","fontSize":"11px","marginBottom":"3px"}),
                html.Div([
                    html.Span(f"{val25:,.1f}", style={"fontSize":"20px","fontWeight":"bold","color":color}),
                    html.Span(f" {unit}", style={"fontSize":"11px","color":"#64748b"})
                ]),
                html.Div([
                    html.Span(f"24年: {val24:,.1f}{unit}", style={"fontSize":"10px","color":"#94a3b8"}),
                    html.Span(f" ({yoy_sign}{yoy:.1f}%)", style={"fontSize":"10px","color":yoy_color,"fontWeight":"bold","marginLeft":"4px"})
                ], style={"marginTop":"2px"})
            ], style={"background":"#fff","padding":"10px 8px","borderRadius":"10px","textAlign":"center"})
        
        sku_25 = dff["宝贝ID"].nunique()
        brand_25 = dff["品牌"].nunique()
        store_25 = dff["宝贝店铺名称"].nunique()
        
        if len(dff_2024) > 0:
            sku_24 = dff_2024["宝贝ID"].nunique()
            brand_24 = dff_2024["品牌"].nunique()
            store_24 = dff_2024["宝贝店铺名称"].nunique()
            sku_yoy = ((sku_25/sku_24 - 1) * 100) if sku_24 > 0 else 0
            brand_yoy = ((brand_25/brand_24 - 1) * 100) if brand_24 > 0 else 0
            store_yoy = ((store_25/store_24 - 1) * 100) if store_24 > 0 else 0
        else:
            sku_24 = brand_24 = store_24 = 0
            sku_yoy = brand_yoy = store_yoy = 0
        
        kpis = [
            kpi_yoy("销售额",ts/1e8,ts_24/1e8,yoy_ts,"亿元","#3b82f6"),
            kpi_yoy("销量",tq/1e8,tq_24/1e8,yoy_tq,"亿件","#f59e0b"),
            kpi_yoy("均价",round(ap,1),round(ap_24,1),yoy_ap,"元","#10b981"),
            kpi_yoy("商品",sku_25,sku_24,sku_yoy,"个","#8b5cf6"),
            kpi_yoy("品牌",brand_25,brand_24,brand_yoy,"个","#ec4899"),
            kpi_yoy("店铺",store_25,store_24,store_yoy,"家","#ef4444")
        ]
    else:
        kpis = [kpi("销售额",ts/1e8,"亿元","#3b82f6"), kpi("销量",tq/1e8,"亿件","#f59e0b"), kpi("均价",round(ap,1),"元","#10b981"), kpi("商品",dff["宝贝ID"].nunique(),"个","#8b5cf6"), kpi("品牌",dff["品牌"].nunique(),"个","#ec4899"), kpi("店铺",dff["宝贝店铺名称"].nunique(),"家","#ef4444")]
    
    show_pct = "pct" in modes
    pbins = [("0-50",0,50),("50-100",50,100),("100-200",100,200),("200-500",200,500),("500-1000",500,1000),("1000+",1000,999999)]
    pcolors = ["#10b981","#f59e0b","#3b82f6","#8b5cf6","#ec4899","#ef4444"]
    
    m = dff.groupby("月份", observed=True)["销售额"].sum().reset_index().sort_values("月份")
    if show_yoy and year != "2024" and dff_2024 is not None:
        m_2024 = dff_2024.groupby("月份", observed=True)["销售额"].sum().reset_index().sort_values("月份")
        m["month_only"] = m["月份"].astype(str).str[-2:]
        m_2024["month_only"] = m_2024["月份"].astype(str).str[-2:]
        f1 = go.Figure()
        f1.add_trace(go.Bar(x=m["month_only"], y=m["销售额"]/1e8, name="2025", marker_color="#3b82f6", text=[f"{v/1e8:.2f}亿" for v in m["销售额"]], textposition="outside"))
        f1.add_trace(go.Bar(x=m_2024["month_only"], y=m_2024["销售额"]/1e8, name="2024", marker_color="#cbd5e1", text=[f"{v/1e8:.2f}亿" for v in m_2024["销售额"]], textposition="outside"))
        f1.update_layout(title="📈 月度销售额对比（亿元）（点击下钻）", yaxis_title="亿元", barmode="group", height=320, margin=dict(l=60,r=60,t=60,b=60), clickmode="event+select", font=dict(size=12))
    elif show_pct:
        mp = (m["销售额"]/m["销售额"].sum()*100).round(1)
        f1 = go.Figure(go.Bar(x=m["月份"], y=mp, marker_color="#3b82f6", text=[f"{v:.1f}%" for v in mp], textposition="outside"))
        f1.update_layout(title="📈 月度占比（%）（点击下钻）", yaxis=dict(range=[0,100]), height=260, margin=dict(l=40,r=40,t=40,b=40), clickmode="event+select")
    else:
        f1 = go.Figure(go.Bar(x=m["月份"], y=m["销售额"]/1e8, marker_color="#3b82f6", text=[f"{v/1e8:.1f}亿" for v in m["销售额"]], textposition="outside"))
        f1.update_layout(title="📈 月度销售额（亿元）（点击下钻）", yaxis_title="亿元", height=260, margin=dict(l=40,r=40,t=40,b=40), clickmode="event+select")
    
    c1 = dff.groupby("Lv1类目名称(逐月固定)", observed=True)["销售额"].sum().sort_values(ascending=False).head(8)
    if show_yoy and year != "2024":
        c1_2024 = dff_2024.groupby("Lv1类目名称(逐月固定)", observed=True)["销售额"].sum().sort_values(ascending=False).head(8)
        f2 = go.Figure()
        f2.add_trace(go.Bar(x=c1.index, y=c1.values/1e8, name="2025", marker_color="#8b5cf6", text=[f"{v/1e8:.2f}亿" for v in c1.values], textposition="outside"))
        f2.add_trace(go.Bar(x=c1_2024.index, y=c1_2024.values/1e8, name="2024", marker_color="#cbd5e1", text=[f"{v/1e8:.2f}亿" for v in c1_2024.values], textposition="outside"))
        f2.update_layout(title="🏷️ 一级类目对比（亿元）（点击下钻）", xaxis_tickangle=-30, yaxis_title="亿元", barmode="group", height=260, margin=dict(l=40,r=40,t=40,b=80), clickmode="event+select")
    elif show_pct:
        c1p = (c1/c1.sum()*100).round(1)
        f2 = go.Figure(go.Bar(x=c1.index, y=c1p.values, marker_color="#8b5cf6", text=[f"{v:.1f}%" for v in c1p.values], textposition="outside"))
        f2.update_layout(title="🏷️ 一级类目占比（%）（点击下钻）", xaxis_tickangle=-30, yaxis=dict(range=[0,100]), height=260, margin=dict(l=40,r=40,t=40,b=80), clickmode="event+select")
    else:
        f2 = go.Figure(go.Bar(x=c1.index, y=c1.values/1e8, marker_color="#8b5cf6", text=[f"{v/1e8:.2f}亿" for v in c1.values], textposition="outside"))
        f2.update_layout(title="🏷️ 一级类目分布（点击下钻）", xaxis_tickangle=-30, yaxis_title="亿元", height=260, margin=dict(l=40,r=40,t=40,b=80), clickmode="event+select")
    
    c2 = dff.groupby("Lv2类目名称(逐月固定)", observed=True)["销售额"].sum().sort_values(ascending=False).head(12)
    if show_yoy and year != "2024":
        c2_2024 = dff_2024.groupby("Lv2类目名称(逐月固定)", observed=True)["销售额"].sum().sort_values(ascending=False).head(12)
        f3 = go.Figure()
        f3.add_trace(go.Bar(x=c2.index, y=c2.values/1e8, name="2025", marker_color="#10b981", text=[f"{v/1e8:.2f}亿" for v in c2.values], textposition="outside"))
        f3.add_trace(go.Bar(x=c2_2024.index, y=c2_2024.values/1e8, name="2024", marker_color="#cbd5e1", text=[f"{v/1e8:.2f}亿" for v in c2_2024.values], textposition="outside"))
        f3.update_layout(title="🏷️ 二级类目对比（亿元）（点击下钻）", xaxis_tickangle=-45, yaxis_title="亿元", barmode="group", height=260, margin=dict(l=40,r=40,t=40,b=130), clickmode="event+select")
    elif show_pct:
        c2p = (c2/c2.sum()*100).round(1)
        f3 = go.Figure(go.Bar(x=c2.index, y=c2p.values, marker_color="#10b981", text=[f"{v:.1f}%" for v in c2p.values], textposition="outside"))
        f3.update_layout(title="🏷️ 二级类目占比（%）（点击下钻）", xaxis_tickangle=-45, yaxis=dict(range=[0,100]), height=260, margin=dict(l=40,r=40,t=40,b=130), clickmode="event+select")
    else:
        f3 = go.Figure(go.Bar(x=c2.index, y=c2.values/1e8, marker_color="#10b981", text=[f"{v/1e8:.2f}亿" for v in c2.values], textposition="outside"))
        f3.update_layout(title="🏷️ 二级类目分布（点击下钻）", xaxis_tickangle=-45, yaxis_title="亿元", height=260, margin=dict(l=40,r=40,t=40,b=130), clickmode="event+select")
    
    try:
        price_labels = ["0-50","50-100","100-200","200-500","500-1000","1000+"]
        dff_copy = dff[dff["成交均价"].notna()].copy()
        if len(dff_copy) > 0:
            dff_copy["价格区间"] = pd.cut(dff_copy["成交均价"], bins=[0,50,100,200,500,1000,999999], labels=price_labels, include_lowest=True)
            ps = dff_copy.groupby("价格区间", observed=True)["销售额"].sum().reindex(price_labels, fill_value=0).tolist()
        else:
            ps = [0]*6
    except:
        ps = [0]*6
    
    if show_yoy and year != "2024" and dff_2024 is not None and len(dff_2024) > 0:
        try:
            dff_2024_copy = dff_2024[dff_2024["成交均价"].notna()].copy()
            dff_2024_copy["价格区间"] = pd.cut(dff_2024_copy["成交均价"], bins=[0,50,100,200,500,1000,999999], labels=price_labels, include_lowest=True)
            ps_2024 = dff_2024_copy.groupby("价格区间", observed=True)["销售额"].sum().reindex(price_labels, fill_value=0).tolist()
        except:
            ps_2024 = [0]*6
        f4 = go.Figure()
        f4.add_trace(go.Bar(x=price_labels, y=[p/1e8 for p in ps], name="2025", marker_color="#f59e0b", text=[f"{p/1e8:.1f}亿" for p in ps], textposition="outside"))
        f4.add_trace(go.Bar(x=price_labels, y=[p/1e8 for p in ps_2024], name="2024", marker_color="#cbd5e1", text=[f"{p/1e8:.1f}亿" for p in ps_2024], textposition="outside"))
        f4.update_layout(title="💰 价格区间对比（亿元）（点击下钻）", yaxis_title="亿元", barmode="group", height=260, margin=dict(l=40,r=40,t=40,b=50), clickmode="event+select")
    elif show_pct:
        pt = sum(ps); pp = [p/pt*100 for p in ps] if pt>0 else ps
        f4 = go.Figure(go.Bar(x=[l for l,_,_ in pbins], y=pp, marker_color=pcolors, text=[f"{v:.1f}%" for v in pp], textposition="outside"))
        f4.update_layout(title="💰 价格区间占比（%）（点击下钻）", yaxis=dict(range=[0,100]), height=260, margin=dict(l=40,r=40,t=40,b=50), clickmode="event+select")
    else:
        f4 = go.Figure(go.Bar(x=[l for l,_,_ in pbins], y=[p/1e8 for p in ps], marker_color=pcolors, text=[f"{p/1e8:.1f}亿" for p in ps], textposition="outside"))
        f4.update_layout(title="💰 价格区间（点击下钻）", yaxis_title="亿元", height=260, margin=dict(l=40,r=40,t=40,b=50), clickmode="event+select")
    
    pdata = dff.groupby("平台", observed=True)["销售额"].sum().sort_values(ascending=False)
    if show_yoy and year != "2024":
        pdata_2024 = dff_2024.groupby("平台", observed=True)["销售额"].sum().sort_values(ascending=False)
        f5 = go.Figure()
        f5.add_trace(go.Bar(x=pdata.index, y=pdata.values/1e8, name="2025", marker_color="#06b6d4", text=[f"{v/1e8:.2f}亿" for v in pdata.values], textposition="outside"))
        f5.add_trace(go.Bar(x=pdata_2024.index, y=pdata_2024.values/1e8, name="2024", marker_color="#cbd5e1", text=[f"{v/1e8:.2f}亿" for v in pdata_2024.values], textposition="outside"))
        f5.update_layout(title="📦 平台对比（亿元）（点击下钻）", yaxis_title="亿元", barmode="group", height=260, margin=dict(l=40,r=40,t=40,b=50), clickmode="event+select")
    elif show_pct:
        pp = (pdata/pdata.sum()*100).round(1)
        f5 = go.Figure(go.Bar(x=pdata.index, y=pp.values, marker_color="#06b6d4", text=[f"{v:.1f}%" for v in pp.values], textposition="outside"))
        f5.update_layout(title="📦 平台占比（%）（点击下钻）", yaxis=dict(range=[0,100]), height=260, margin=dict(l=40,r=40,t=40,b=50), clickmode="event+select")
    else:
        f5 = go.Figure(go.Bar(x=pdata.index, y=pdata.values/1e8, marker_color="#06b6d4", text=[f"{v/1e8:.2f}亿" for v in pdata.values], textposition="outside"))
        f5.update_layout(title="📦 平台分布（点击下钻）", yaxis_title="亿元", height=260, margin=dict(l=40,r=40,t=40,b=50), clickmode="event+select")
    
    b = dff.groupby("品牌", observed=True)["销售额"].sum().sort_values(ascending=False).head(10)
    if show_yoy and year != "2024":
        b_2024 = dff_2024.groupby("品牌", observed=True)["销售额"].sum()
        b_2024 = b_2024.reindex(b.index, fill_value=0)
        f6 = go.Figure()
        f6.add_trace(go.Bar(y=b_2024.index[::-1], x=b_2024.values[::-1]/1e8, name="2024", orientation="h", marker_color="#cbd5e1", text=[f"{v/1e8:.2f}亿" if v>0 else "" for v in b_2024.values[::-1]], textposition="outside"))
        f6.add_trace(go.Bar(y=b.index[::-1], x=b.values[::-1]/1e8, name="2025", orientation="h", marker_color="#ec4899", text=[f"{v/1e8:.2f}亿" for v in b.values[::-1]], textposition="outside"))
        f6.update_layout(title="🏆 品牌 Top10 对比（亿元）（点击下钻）", xaxis_title="亿元", barmode="group", height=300, margin=dict(l=120,r=80,t=40,b=40), clickmode="event+select")
    elif show_pct:
        bp = (b/b.sum()*100).round(1)
        f6 = go.Figure(go.Bar(y=b.index[::-1], x=bp.values[::-1], orientation="h", marker_color="#ec4899", text=[f"{v:.1f}%" for v in bp.values[::-1]], textposition="outside"))
        f6.update_layout(title="🏆 品牌 Top10（%）（点击下钻）", xaxis=dict(range=[0,100]), height=260, margin=dict(l=120,r=70,t=40,b=40), clickmode="event+select")
    else:
        f6 = go.Figure(go.Bar(y=b.index[::-1], x=b.values[::-1]/1e8, orientation="h", marker_color="#ec4899", text=[f"{v/1e8:.2f}亿" for v in b.values[::-1]], textposition="outside"))
        f6.update_layout(title="🏆 品牌 Top10（亿元）（点击下钻）", xaxis_title="亿元", height=260, margin=dict(l=120,r=80,t=40,b=40), clickmode="event+select")
    
    brand_agg = dff.groupby("品牌", observed=True).agg({"销售额":"sum","销量":"sum","宝贝ID":"nunique"}).reset_index().sort_values("销售额", ascending=False).head(100)
    brand_agg["排名"] = range(1,len(brand_agg)+1)
    brand_agg["销售额(亿)"] = (brand_agg["销售额"]/1e8).round(3)
    brand_agg["销量(万)"] = (brand_agg["销量"]/1e4).round(1)
    brand_agg = brand_agg[["排名","品牌","销售额(亿)","销量(万)","宝贝ID"]]
    brand_agg.columns = ["排名","品牌名称","销售额(亿)","销量(万)","商品数"]
    store_agg = dff.groupby("宝贝店铺名称", observed=True).agg({"销售额":"sum","销量":"sum","宝贝ID":"nunique"}).reset_index().sort_values("销售额", ascending=False).head(100)
    store_agg["排名"] = range(1,len(store_agg)+1)
    store_agg["销售额(亿)"] = (store_agg["销售额"]/1e8).round(3)
    store_agg["销量(万)"] = (store_agg["销量"]/1e4).round(1)
    
    if show_yoy and year != "2024":
        store_2024 = dff_2024.groupby("宝贝店铺名称", observed=True).agg({"销售额":"sum"}).reset_index()
        store_2024.columns = ["宝贝店铺名称", "销售额_2024"]
        store_agg = store_agg.merge(store_2024, on="宝贝店铺名称", how="left")
        store_agg["销售额_2024"] = store_agg["销售额_2024"].fillna(0)
        store_agg["YOY(%)"] = ((store_agg["销售额"] / store_agg["销售额_2024"].replace(0, 1) - 1) * 100).round(1)
        store_2024_rank = dff_2024.groupby("宝贝店铺名称", observed=True).agg({"销售额":"sum"}).reset_index().sort_values("销售额", ascending=False).reset_index(drop=True)
        store_2024_rank["排名_2024"] = range(1, len(store_2024_rank)+1)
        store_agg = store_agg.merge(store_2024_rank[["宝贝店铺名称","排名_2024"]], on="宝贝店铺名称", how="left")
        store_agg["排名变化"] = store_agg["排名_2024"] - store_agg["排名"]
        store_agg["排名变化"] = store_agg["排名变化"].fillna(0).astype(int)
        store_agg["排名变化显示"] = store_agg.apply(lambda r: f"{'↑' if r['排名变化']>0 else '↓' if r['排名变化']<0 else '→'} {abs(r['排名变化'])}", axis=1)
        store_agg["YOY显示"] = store_agg.apply(lambda r: f"{r['YOY(%)']:.1f}%", axis=1)
        store_agg = store_agg[["排名","排名变化显示","宝贝店铺名称","销售额(亿)","销量(万)","宝贝ID","YOY显示"]]
        store_agg.columns = ["排名","排名变化","店铺名称","销售额(亿)","销量(万)","商品数","YOY(%)"]
    else:
        store_agg = store_agg[["排名","宝贝店铺名称","销售额(亿)","销量(万)","宝贝ID"]]
        store_agg.columns = ["排名","店铺名称","销售额(亿)","销量(万)","商品数"]
    
    store_table = make_table(store_agg, store_agg.columns.tolist(), height=380)
    
    return [kpis, f1, f2, f3, f4, f5, f6, store_table, status, {"display":"none"}]

@app.callback([Output("drill-section","style"), Output("drill-title","children"), Output("d-monthly","figure"), Output("d-price","figure"), Output("d-store-table","children"), Output("d-product-table","children")], [Input("g-trend","clickData"), Input("g-cat1","clickData"), Input("g-cat2","clickData"), Input("g-price","clickData"), Input("g-platform","clickData"), Input("g-brand","clickData"), Input("btn-close-drill","n_clicks")], [State("dd-year","value"), State("dd-month","value"), State("dd-cat1","value"), State("dd-cat2","value"), State("dd-brand","value"), State("dd-platform","value"), State("dd-price","value"), State("yoy-toggle","value")])
def handle_drill(c_trend, c_cat1, c_cat2, c_price, c_platform, c_brand, close_n, year, months, cat1, cat2, brands, platforms, prices, yoy_val):
    ctx = dash.callback_context
    t = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
    if t == "btn-close-drill" or not t: return [{"display":"none"}, "", go.Figure(), go.Figure(), "", ""]
    if not ctx.triggered[0].get("value"): return [{"display":"none"}, "", go.Figure(), go.Figure(), "", ""]
    
    if year and year != "all":
        base = df[df["年份"]==int(year)]
    else:
        base = df
    
    base_dff = filter_df(base, months, cat1, cat2, brands, platforms, prices)
    
    show_yoy = "yoy" in yoy_val
    months_2024 = None
    base_dff_2024 = None
    drill_2024 = None
    if show_yoy and year != "2024":
        if months:
            months_2024 = []
            for m in months:
                m_str = str(m)
                months_2024.append(int(m_str.replace("2025", "2024")) if "2025" in m_str else int(m_str))
        base_dff_2024 = filter_df(df[df["年份"]==2024], months_2024, cat1, cat2, brands, platforms, prices)
        drill_2024 = base_dff_2024.copy()
    
    title = ""
    
    if t == "g-trend" and c_trend:
        mon = c_trend["points"][0]["x"]
        base_dff = base_dff[base_dff["月份"]==mon]
        title = f"📅 月份「{mon}」"
    elif t == "g-cat1" and c_cat1:
        name = c_cat1["points"][0]["x"]
        base_dff = base_dff[base_dff["Lv1类目名称(逐月固定)"]==name]
        title = f"🏷️ 一级类目「{name}」"
    elif t == "g-cat2" and c_cat2:
        name = c_cat2["points"][0]["x"]
        base_dff = base_dff[base_dff["Lv2类目名称(逐月固定)"]==name]
        title = f"🏷️ 二级类目「{name}」"
    elif t == "g-price" and c_price:
        labels = ["0-50","50-100","100-200","200-500","500-1000","1000+"]
        idx = c_price["points"][0]["pointIndex"]
        p = labels[idx]
        lo, hi = PRICE_BINS[p]
        base_dff = base_dff[(base_dff["成交均价"]>=lo)&(base_dff["成交均价"]<hi)]
        title = f"💰 价格区间「{p}」"
    elif t == "g-platform" and c_platform:
        name = c_platform["points"][0]["x"]
        base_dff = base_dff[base_dff["平台"]==name]
        title = f"📦 平台「{name}」"
    elif t == "g-brand" and c_brand:
        name = c_brand["points"][0]["y"]
        base_dff = base_dff[base_dff["品牌"]==name]
        title = f"🏢 品牌「{name}」"
    else:
        return [{"display":"none"}, "", go.Figure(), go.Figure(), "", ""]
    
    m = base_dff.groupby("月份", observed=True)["销售额"].sum().reset_index().sort_values("月份")
    if show_yoy and year != "2024" and base_dff_2024 is not None:
        drill_2024 = base_dff_2024.copy()
        if t == "g-trend" and c_trend:
            mon = c_trend["points"][0]["x"]
            mon_2024 = mon.replace("2025", "2024") if "2025" in mon else mon
            drill_2024 = drill_2024[drill_2024["月份"]==mon_2024]
        elif t == "g-cat1" and c_cat1:
            name = c_cat1["points"][0]["x"]
            drill_2024 = drill_2024[drill_2024["Lv1类目名称(逐月固定)"]==name]
        elif t == "g-cat2" and c_cat2:
            name = c_cat2["points"][0]["x"]
            drill_2024 = drill_2024[drill_2024["Lv2类目名称(逐月固定)"]==name]
        elif t == "g-price" and c_price:
            labels = ["0-50","50-100","100-200","200-500","500-1000","1000+"]
            idx = c_price["points"][0]["pointIndex"]
            p = labels[idx]
            lo, hi = PRICE_BINS[p]
            drill_2024 = drill_2024[(drill_2024["成交均价"]>=lo)&(drill_2024["成交均价"]<hi)]
        elif t == "g-platform" and c_platform:
            name = c_platform["points"][0]["x"]
            drill_2024 = drill_2024[drill_2024["平台"]==name]
        elif t == "g-brand" and c_brand:
            name = c_brand["points"][0]["y"]
            drill_2024 = drill_2024[drill_2024["品牌"]==name]
        
        m_2024 = drill_2024.groupby("月份", observed=True)["销售额"].sum().reset_index().sort_values("月份")
        m["month_only"] = m["月份"].astype(str).str[-2:]
        m_2024["month_only"] = m_2024["月份"].astype(str).str[-2:]
        
        fm = go.Figure()
        fm.add_trace(go.Bar(x=m["month_only"], y=m["销售额"]/1e8, name="2025", marker_color="#3b82f6", text=[f"{v/1e8:.1f}亿" for v in m["销售额"]], textposition="outside"))
        fm.add_trace(go.Bar(x=m_2024["month_only"], y=m_2024["销售额"]/1e8, name="2024", marker_color="#cbd5e1", text=[f"{v/1e8:.1f}亿" for v in m_2024["销售额"]], textposition="outside"))
        fm.update_layout(title="📈 月度趋势对比", yaxis_title="亿元", barmode="group", height=200, margin=dict(l=40,r=40,t=40,b=40))
    else:
        fm = go.Figure(go.Bar(x=m["月份"], y=m["销售额"]/1e8, marker_color="#3b82f6", text=[f"{v/1e8:.1f}亿" for v in m["销售额"]], textposition="outside"))
        fm.update_layout(title="📈 月度趋势", yaxis_title="亿元", height=200, margin=dict(l=40,r=40,t=40,b=40))
    
    pbins = [("0-50",0,50),("50-100",50,100),("100-200",100,200),("200-500",200,500),("500-1000",500,1000),("1000+",1000,999999)]
    pcolors = ["#10b981","#f59e0b","#3b82f6","#8b5cf6","#ec4899","#ef4444"]
    ps = [base_dff[(base_dff["成交均价"]>=lo)&(base_dff["成交均价"]<hi)]["销售额"].sum() for _,lo,hi in pbins]
    
    if show_yoy and year != "2024" and base_dff_2024 is not None:
        ps_2024 = [drill_2024[(drill_2024["成交均价"]>=lo)&(drill_2024["成交均价"]<hi)]["销售额"].sum() for _,lo,hi in pbins]
        fp = go.Figure()
        fp.add_trace(go.Bar(x=[l for l,_,_ in pbins], y=[p/1e8 for p in ps], name="2025", marker_color="#f59e0b", text=[f"{p/1e8:.1f}亿" for p in ps], textposition="outside"))
        fp.add_trace(go.Bar(x=[l for l,_,_ in pbins], y=[p/1e8 for p in ps_2024], name="2024", marker_color="#cbd5e1", text=[f"{p/1e8:.1f}亿" for p in ps_2024], textposition="outside"))
        fp.update_layout(title="💰 价格区间对比", yaxis_title="亿元", barmode="group", height=200, margin=dict(l=40,r=40,t=40,b=50))
    else:
        fp = go.Figure(go.Bar(x=[l for l,_,_ in pbins], y=[p/1e8 for p in ps], marker_color=pcolors, text=[f"{p/1e8:.1f}亿" for p in ps], textposition="outside"))
        fp.update_layout(title="💰 价格区间", yaxis_title="亿元", height=200, margin=dict(l=40,r=40,t=40,b=50))
    
    store_agg = base_dff.groupby("宝贝店铺名称", observed=True).agg({"销售额":"sum","销量":"sum","宝贝ID":"nunique"}).reset_index().sort_values("销售额",ascending=False).head(100)
    store_agg["排名"] = range(1,len(store_agg)+1)
    store_agg["销售额(亿)"] = (store_agg["销售额"]/1e8).round(3)
    store_agg["销量(万)"] = (store_agg["销量"]/1e4).round(1)
    
    if show_yoy and year != "2024" and base_dff_2024 is not None:
        store_2024 = drill_2024.groupby("宝贝店铺名称", observed=True).agg({"销售额":"sum"}).reset_index()
        store_2024.columns = ["宝贝店铺名称", "销售额_2024"]
        store_agg = store_agg.merge(store_2024, on="宝贝店铺名称", how="left")
        store_agg["销售额_2024"] = store_agg["销售额_2024"].fillna(0)
        store_agg["同比"] = store_agg.apply(lambda x: f"{((x['销售额']/x['销售额_2024']-1)*100):+.1f}%" if x['销售额_2024']>0 else "-", axis=1)
        store_agg["销售额_24(亿)"] = (store_agg["销售额_2024"]/1e8).round(3)
        store_agg = store_agg[["排名","宝贝店铺名称","销售额(亿)","销售额_24(亿)","同比","销量(万)","宝贝ID"]]
        store_agg.columns = ["排名","店铺名称","销售额(亿)","24年(亿)","同比","销量(万)","商品数"]
        store_cols = ["排名","店铺名称","销售额(亿)","24年(亿)","同比","销量(万)","商品数"]
    else:
        store_agg = store_agg[["排名","宝贝店铺名称","销售额(亿)","销量(万)","宝贝ID"]]
        store_agg.columns = ["排名","店铺名称","销售额(亿)","销量(万)","商品数"]
        store_cols = ["排名","店铺名称","销售额(亿)","销量(万)","商品数"]
    
    prod_agg = base_dff.groupby(["宝贝ID","宝贝名称"], observed=True).agg({"销售额":"sum","销量":"sum"}).reset_index().sort_values("销售额",ascending=False).head(100)
    prod_agg["排名"] = range(1,len(prod_agg)+1)
    prod_agg["销售额(万)"] = (prod_agg["销售额"]/1e4).round(1)
    
    if show_yoy and year != "2024" and base_dff_2024 is not None and drill_2024 is not None:
        prod_2024 = drill_2024.groupby(["宝贝ID"], observed=True).agg({"销售额":"sum"}).reset_index()
        prod_2024.columns = ["宝贝ID", "销售额_2024"]
        prod_agg = prod_agg.merge(prod_2024, on="宝贝ID", how="left")
        prod_agg["销售额_2024"] = prod_agg["销售额_2024"].fillna(0)
        prod_agg["同比"] = prod_agg.apply(lambda x: f"{((x['销售额']/x['销售额_2024']-1)*100):+.1f}%" if x['销售额_2024']>0 else "-", axis=1)
        prod_agg["销售额_24(万)"] = (prod_agg["销售额_2024"]/1e4).round(1)
        prod_agg = prod_agg[["排名","宝贝ID","宝贝名称","销售额(万)","销售额_24(万)","同比","销量"]]
        prod_agg.columns = ["排名","SKU","商品名称","销售额(万)","24年(万)","同比","销量(件)"]
        prod_cols = ["排名","SKU","商品名称","销售额(万)","24年(万)","同比","销量(件)"]
    else:
        prod_agg = prod_agg[["排名","宝贝ID","宝贝名称","销售额(万)","销量"]]
        prod_agg.columns = ["排名","SKU","商品名称","销售额(万)","销量(件)"]
        prod_cols = ["排名","SKU","商品名称","销售额(万)","销量(件)"]
    
    return [{"display":"block","background":"#f0fdf4","padding":"15px","borderRadius":"12px"}, f"🔍 {title} 详细分析", fm, fp, make_table(store_agg, store_cols), make_table(prod_agg, prod_cols)]

if __name__ == "__main__":
    import socket
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except:
        local_ip = "172.16.60.187"
    print(f"\n🚀 情报通 2024-2025 V10")
    print(f"💻 本机访问:     http://127.0.0.1:8050")
    print(f"📱 局域网访问:   http://{local_ip}:8050\n")
    app.run(debug=False, host="0.0.0.0", port=8050)