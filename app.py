#!/usr/bin/env python3
"""情报通 2025 全年数据看板 V9 - 修复类目点击"""
import os, tempfile, shutil, gzip, requests
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, html, dcc, callback, Output, Input, State
from dash.dash_table import DataTable
import dash

# ========== 数据加载：从 GitHub Release 下载 gz 并解压 ==========
_DATA_DIR = os.path.join(tempfile.gettempdir(), "qingbaotong_data")
os.makedirs(_DATA_DIR, exist_ok=True)
_PKL_PATH = os.path.join(_DATA_DIR, "qingbaotong_2025_full.pkl")
_GZ_URL = "https://github.com/Julian0921/qingbaotong-dashboard/releases/download/v1.0/qingbaotong_2025_full.pkl.gz"

def _ensure_data():
    if os.path.exists(_PKL_PATH):
        print("✅ 数据文件已存在，直接加载")
        return
    print(f"📥 从 GitHub Release 下载数据...")
    gz_path = _PKL_PATH + ".gz"
    r = requests.get(_GZ_URL, stream=True, timeout=600)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    downloaded = 0
    with open(gz_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=10*1024*1024):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r  下载进度: {pct}% ({downloaded//1024//1024}/{total//1024//1024}MB)", end="", flush=True)
    print("\n📦 解压中...")
    with gzip.open(gz_path, "rb") as fin:
        with open(_PKL_PATH, "wb") as fout:
            shutil.copyfileobj(fin, fout)
    os.remove(gz_path)
    size_mb = os.path.getsize(_PKL_PATH) / 1e6
    print(f"✅ 数据准备完成 ({size_mb:.1f}MB)")

_ensure_data()
print("加载数据...")
df = pd.read_pickle(_PKL_PATH)
df["品牌"] = df["宝贝品牌(bid)"].fillna("未知品牌")
df["月份"] = df["月"].astype(str)

CAT1_TO_CAT2 = {}
for c1 in df["Lv1类目名称(逐月固定)"].unique():
    CAT1_TO_CAT2[c1] = sorted(df[df["Lv1类目名称(逐月固定)"]==c1]["Lv2类目名称(逐月固定)"].unique().tolist())

ALL_CAT1 = sorted(df["Lv1类目名称(逐月固定)"].unique())
ALL_CAT2 = sorted(df["Lv2类目名称(逐月固定)"].unique())
ALL_BRANDS = df["品牌"].value_counts().head(80).index.tolist()
ALL_PLATFORMS = sorted(df["平台"].unique().tolist())
print(f"✅ {len(df):,} 行")

app = Dash(__name__)
app.title = "情报通 2025 V9"
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
    if months: dff = dff[dff["月份"].isin(months)]
    if cat1: dff = dff[dff["Lv1类目名称(逐月固定)"].isin(cat1)]
    if cat2: dff = dff[dff["Lv2类目名称(逐月固定)"].isin(cat2)]
    if brands: dff = dff[dff["品牌"].isin(brands)]
    if platforms: dff = dff[dff["平台"].isin(platforms)]
    if prices:
        mask = pd.Series(False, index=dff.index)
        for p in prices:
            if p in PRICE_BINS:
                lo, hi = PRICE_BINS[p]
                mask |= (dff["成交均价"]>=lo) & (dff["成交均价"]<hi)
        dff = dff[mask]
    return dff

def make_table(data, cols, height=320):
    return DataTable(
        data=data.to_dict("records"),
        columns=[{"name":c,"id":c} for c in cols],
        page_size=20, page_action="native",
        style_cell={"padding":"5px","fontSize":"11px","textAlign":"center"},
        style_header={"background":"#f1f5f9","fontWeight":"bold","fontSize":"12px"},
        style_data_conditional=[{"if":{"row_index":"odd"},"background":"#f8fafc"}],
        style_table={"maxHeight":f"{height}px","overflowY":"auto"}
    )

brand_cnt = df["品牌"].nunique()
row_cnt = len(df)
app.layout = html.Div([
    html.Div([
        html.H1("📊 情报通 2025 全年数据看板 V9", style={"color":"#1e293b","margin":"0","fontSize":"24px"}),
        html.Div([html.Span(f"📦 {row_cnt:,} 条 | 🏢 {brand_cnt:,} 品牌")], style={"color":"#64748b","margin":"6px 0 0 0","fontSize":"12px"})
    ], style={"textAlign":"center","padding":"18px","background":"#fff","borderRadius":"12px","marginBottom":"12px"}),
    html.Div(id="kpi-row", style={"display":"grid","gridTemplateColumns":"repeat(6,1fr)","gap":"10px","marginBottom":"12px"}),
    html.Div([
        html.Div([html.Div("📅 月份"), dcc.Dropdown(id="dd-month", multi=True, placeholder="全部")], style={"width":"120px"}),
        html.Div([html.Div("🏷️ 一级类目", style={"color":"#8b5cf6"}), dcc.Dropdown(id="dd-cat1", multi=True, placeholder="选择")], style={"width":"150px"}),
        html.Div([html.Div("🏷️ 二级类目", style={"color":"#10b981"}), dcc.Dropdown(id="dd-cat2", multi=True, placeholder="选择")], style={"width":"150px"}),
        html.Div([html.Div("🏢 品牌"), dcc.Dropdown(id="dd-brand", multi=True, placeholder="全部")], style={"width":"170px"}),
        html.Div([html.Div("🏪 平台"), dcc.Dropdown(id="dd-platform", multi=True, placeholder="全部")], style={"width":"140px"}),
        html.Div([html.Div("💰 价格", style={"color":"#f59e0b"}), dcc.Dropdown(id="dd-price", multi=True, placeholder="全部")], style={"width":"120px"}),
        html.Div([html.Button("✅ 应用", id="btn-apply", n_clicks=0, style={"background":"#3b82f6","color":"white","border":"none","padding":"10px 16px","borderRadius":"8px","cursor":"pointer","fontWeight":"bold"}), html.Button("🔄 重置", id="btn-reset", n_clicks=0, style={"background":"#e2e8f0","border":"none","padding":"10px 14px","borderRadius":"8px","cursor":"pointer","marginLeft":"6px"})], style={"display":"flex","alignItems":"flexEnd"}),
    ], style={"background":"#fff","padding":"14px","borderRadius":"12px","display":"flex","flexWrap":"wrap","alignItems":"flexEnd","gap":"10px","marginBottom":"12px"}),
    html.Div(id="filter-status", style={"background":"#f0f9ff","padding":"8px 12px","borderRadius":"8px","marginBottom":"12px","fontSize":"12px","color":"#3b82f6"}),
    html.Div([html.Span("📊 展示："), dcc.Checklist(id="data-mode", options=[{"label":" 绝对值","value":"abs"},{"label":" 百分比","value":"pct"}], value=["abs"])], style={"background":"#fff","padding":"10px","borderRadius":"8px","marginBottom":"12px"}),
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

@app.callback([Output("dd-month","options"), Output("dd-cat1","options"), Output("dd-cat2","options"), Output("dd-brand","options"), Output("dd-platform","options"), Output("dd-price","options")], [Input("btn-apply","n_clicks")])
def init_dropdowns(n):
    return ([{"label":m,"value":m} for m in sorted(df["月份"].unique())], [{"label":c,"value":c} for c in ALL_CAT1], [{"label":c,"value":c} for c in ALL_CAT2], [{"label":b,"value":b} for b in ALL_BRANDS], [{"label":p,"value":p} for p in ALL_PLATFORMS], [{"label":l,"value":v} for l,v in [("0-50元","0-50"),("50-100元","50-100"),("100-200元","100-200"),("200-500元","200-500"),("500-1000元","500-1000"),("1000+元","1000+")]])

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

@app.callback([Output("kpi-row","children"), Output("g-trend","figure"), Output("g-cat1","figure"), Output("g-cat2","figure"), Output("g-price","figure"), Output("g-platform","figure"), Output("g-brand","figure"), Output("store-table-area","children"), Output("filter-status","children"), Output("drill-section","style")], [Input("btn-apply","n_clicks"), Input("btn-close-drill","n_clicks"), Input("data-mode","value")], [State("dd-month","value"), State("dd-cat1","value"), State("dd-cat2","value"), State("dd-brand","value"), State("dd-platform","value"), State("dd-price","value")])
def update_board(apply_n, close_n, modes, months, cat1, cat2, brands, platforms, prices):
    ctx = dash.callback_context
    t = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""
    if t == "btn-close-drill": return [dash.no_update]*9 + [{"display":"none"}]
    
    if apply_n == 0:
        dff = df; status = "📌 全部数据 | 点击图表下钻"
    else:
        dff = filter_df(df, months, cat1, cat2, brands, platforms, prices)
        parts = []
        if months: parts.append(f"月份{len(months)}个")
        if cat1: parts.append(f"类目{len(cat1)}个")
        if cat2: parts.append(f"子类{len(cat2)}个")
        if brands: parts.append(f"品牌{len(brands)}个")
        status = f"📌 {', '.join(parts) if parts else '全部'} | {len(dff):,} 条"
    
    ts, tq = dff["销售额"].sum(), dff["销量"].sum()
    ap = dff["成交均价"].mean() if len(dff)>0 else 0
    kpis = [kpi("销售额",ts/1e8,"亿元","#3b82f6"), kpi("销量",tq/1e8,"亿件","#f59e0b"), kpi("均价",round(ap,1),"元","#10b981"), kpi("商品",dff["宝贝ID"].nunique(),"个","#8b5cf6"), kpi("品牌",dff["品牌"].nunique(),"个","#ec4899"), kpi("店铺",dff["宝贝店铺名称"].nunique(),"家","#ef4444")]
    
    show_pct = "pct" in modes
    pbins = [("0-50",0,50),("50-100",50,100),("100-200",100,200),("200-500",200,500),("500-1000",500,1000),("1000+",1000,999999)]
    pcolors = ["#10b981","#f59e0b","#3b82f6","#8b5cf6","#ec4899","#ef4444"]
    
    # 月度趋势
    m = dff.groupby("月份")["销售额"].sum().reset_index().sort_values("月份")
    if show_pct:
        mp = (m["销售额"]/m["销售额"].sum()*100).round(1)
        f1 = go.Figure(go.Bar(x=m["月份"], y=mp, marker_color="#3b82f6", text=[f"{v:.1f}%" for v in mp], textposition="outside"))
        f1.update_layout(title="📈 月度占比（%）（点击下钻）", yaxis=dict(range=[0,100]), height=260, margin=dict(l=40,r=40,t=40,b=40), clickmode="event+select")
    else:
        f1 = go.Figure(go.Bar(x=m["月份"], y=m["销售额"]/1e8, marker_color="#3b82f6", text=[f"{v/1e8:.1f}亿" for v in m["销售额"]], textposition="outside"))
        f1.update_layout(title="📈 月度销售额（亿元）（点击下钻）", yaxis_title="亿元", height=260, margin=dict(l=40,r=40,t=40,b=40), clickmode="event+select")
    
    # 一级类目 - 用Bar图
    c1 = dff.groupby("Lv1类目名称(逐月固定)")["销售额"].sum().sort_values(ascending=False).head(8)
    if show_pct:
        c1p = (c1/c1.sum()*100).round(1)
        f2 = go.Figure(go.Bar(x=c1.index, y=c1p.values, marker_color="#8b5cf6", text=[f"{v:.1f}%" for v in c1p.values], textposition="outside"))
        f2.update_layout(title="🏷️ 一级类目占比（%）（点击下钻）", xaxis_tickangle=-30, yaxis=dict(range=[0,100]), height=260, margin=dict(l=40,r=40,t=40,b=80), clickmode="event+select")
    else:
        f2 = go.Figure(go.Bar(x=c1.index, y=c1.values/1e8, marker_color="#8b5cf6", text=[f"{v/1e8:.2f}亿" for v in c1.values], textposition="outside"))
        f2.update_layout(title="🏷️ 一级类目分布（点击下钻）", xaxis_tickangle=-30, yaxis_title="亿元", height=260, margin=dict(l=40,r=40,t=40,b=80), clickmode="event+select")
    
    # 二级类目 - 用Bar图
    c2 = dff.groupby("Lv2类目名称(逐月固定)")["销售额"].sum().sort_values(ascending=False).head(12)
    if show_pct:
        c2p = (c2/c2.sum()*100).round(1)
        f3 = go.Figure(go.Bar(x=c2.index, y=c2p.values, marker_color="#10b981", text=[f"{v:.1f}%" for v in c2p.values], textposition="outside"))
        f3.update_layout(title="🏷️ 二级类目占比（%）（点击下钻）", xaxis_tickangle=-45, yaxis=dict(range=[0,100]), height=260, margin=dict(l=40,r=40,t=40,b=130), clickmode="event+select")
    else:
        f3 = go.Figure(go.Bar(x=c2.index, y=c2.values/1e8, marker_color="#10b981", text=[f"{v/1e8:.2f}亿" for v in c2.values], textposition="outside"))
        f3.update_layout(title="🏷️ 二级类目分布（点击下钻）", xaxis_tickangle=-45, yaxis_title="亿元", height=260, margin=dict(l=40,r=40,t=40,b=130), clickmode="event+select")
    
    # 价格区间
    ps = [dff[(dff["成交均价"]>=lo)&(dff["成交均价"]<hi)]["销售额"].sum() for _,lo,hi in pbins]
    if show_pct:
        pt = sum(ps); pp = [p/pt*100 for p in ps] if pt>0 else ps
        f4 = go.Figure(go.Bar(x=[l for l,_,_ in pbins], y=pp, marker_color=pcolors, text=[f"{v:.1f}%" for v in pp], textposition="outside"))
        f4.update_layout(title="💰 价格区间占比（%）（点击下钻）", yaxis=dict(range=[0,100]), height=260, margin=dict(l=40,r=40,t=40,b=50), clickmode="event+select")
    else:
        f4 = go.Figure(go.Bar(x=[l for l,_,_ in pbins], y=[p/1e8 for p in ps], marker_color=pcolors, text=[f"{p/1e8:.1f}亿" for p in ps], textposition="outside"))
        f4.update_layout(title="💰 价格区间（点击下钻）", yaxis_title="亿元", height=260, margin=dict(l=40,r=40,t=40,b=50), clickmode="event+select")
    
    # 平台 - 用Bar图
    pdata = dff.groupby("平台")["销售额"].sum().sort_values(ascending=False)
    if show_pct:
        pp = (pdata/pdata.sum()*100).round(1)
        f5 = go.Figure(go.Bar(x=pdata.index, y=pp.values, marker_color="#06b6d4", text=[f"{v:.1f}%" for v in pp.values], textposition="outside"))
        f5.update_layout(title="📦 平台占比（%）（点击下钻）", yaxis=dict(range=[0,100]), height=260, margin=dict(l=40,r=40,t=40,b=50), clickmode="event+select")
    else:
        f5 = go.Figure(go.Bar(x=pdata.index, y=pdata.values/1e8, marker_color="#06b6d4", text=[f"{v/1e8:.2f}亿" for v in pdata.values], textposition="outside"))
        f5.update_layout(title="📦 平台分布（点击下钻）", yaxis_title="亿元", height=260, margin=dict(l=40,r=40,t=40,b=50), clickmode="event+select")
    
    # 品牌 Top10
    b = dff.groupby("品牌")["销售额"].sum().sort_values(ascending=False).head(10)
    if show_pct:
        bp = (b/b.sum()*100).round(1)
        f6 = go.Figure(go.Bar(y=b.index[::-1], x=bp.values[::-1], orientation="h", marker_color="#ec4899", text=[f"{v:.1f}%" for v in bp.values[::-1]], textposition="outside"))
        f6.update_layout(title="🏆 品牌 Top10（%）（点击下钻）", xaxis=dict(range=[0,100]), height=260, margin=dict(l=120,r=70,t=40,b=40), clickmode="event+select")
    else:
        f6 = go.Figure(go.Bar(y=b.index[::-1], x=b.values[::-1]/1e8, orientation="h", marker_color="#ec4899", text=[f"{v/1e8:.2f}亿" for v in b.values[::-1]], textposition="outside"))
        f6.update_layout(title="🏆 品牌 Top10（亿元）（点击下钻）", xaxis_title="亿元", height=260, margin=dict(l=120,r=80,t=40,b=40), clickmode="event+select")
    
    # 品牌Top100表格
    brand_agg = dff.groupby("品牌").agg({"销售额":"sum","销量":"sum","宝贝ID":"nunique"}).reset_index().sort_values("销售额", ascending=False).head(100)
    brand_agg["排名"] = range(1,len(brand_agg)+1)
    brand_agg["销售额(亿)"] = (brand_agg["销售额"]/1e8).round(3)
    brand_agg["销量(万)"] = (brand_agg["销量"]/1e4).round(1)
    brand_agg = brand_agg[["排名","品牌","销售额(亿)","销量(万)","宝贝ID"]]
    brand_agg.columns = ["排名","品牌名称","销售额(亿)","销量(万)","商品数"]
    # 店铺Top100表格
    store_agg = dff.groupby("宝贝店铺名称").agg({"销售额":"sum","销量":"sum","宝贝ID":"nunique"}).reset_index().sort_values("销售额", ascending=False).head(100)
    store_agg["排名"] = range(1,len(store_agg)+1)
    store_agg["销售额(亿)"] = (store_agg["销售额"]/1e8).round(3)
    store_agg["销量(万)"] = (store_agg["销量"]/1e4).round(1)
    store_agg = store_agg[["排名","宝贝店铺名称","销售额(亿)","销量(万)","宝贝ID"]]
    store_agg.columns = ["排名","店铺名称","销售额(亿)","销量(万)","商品数"]
    store_table = make_table(store_agg, ["排名","店铺名称","销售额(亿)","销量(万)","商品数"], height=380)
    
    return [kpis, f1, f2, f3, f4, f5, f6, store_table, status, {"display":"none"}]

# 下钻回调
@app.callback([Output("drill-section","style"), Output("drill-title","children"), Output("d-monthly","figure"), Output("d-price","figure"), Output("d-store-table","children"), Output("d-product-table","children")], [Input("g-trend","clickData"), Input("g-cat1","clickData"), Input("g-cat2","clickData"), Input("g-price","clickData"), Input("g-platform","clickData"), Input("g-brand","clickData"), Input("btn-close-drill","n_clicks")], [State("dd-month","value"), State("dd-cat1","value"), State("dd-cat2","value"), State("dd-brand","value"), State("dd-platform","value"), State("dd-price","value")])
def handle_drill(c_trend, c_cat1, c_cat2, c_price, c_platform, c_brand, close_n, months, cat1, cat2, brands, platforms, prices):
    ctx = dash.callback_context
    t = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
    if t == "btn-close-drill" or not t: return [{"display":"none"}, "", go.Figure(), go.Figure(), "", ""]
    if not ctx.triggered[0].get("value"): return [{"display":"none"}, "", go.Figure(), go.Figure(), "", ""]
    
    base_dff = filter_df(df, months, cat1, cat2, brands, platforms, prices)
    title = ""
    
    # 所有图表都用Bar图，点击数据从points[0]['x']获取
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
    
    # 下钻详情
    m = base_dff.groupby("月份")["销售额"].sum().reset_index().sort_values("月份")
    fm = go.Figure(go.Bar(x=m["月份"], y=m["销售额"]/1e8, marker_color="#3b82f6", text=[f"{v/1e8:.1f}亿" for v in m["销售额"]], textposition="outside"))
    fm.update_layout(title="📈 月度趋势", yaxis_title="亿元", height=200, margin=dict(l=40,r=40,t=40,b=40))
    
    pbins = [("0-50",0,50),("50-100",50,100),("100-200",100,200),("200-500",200,500),("500-1000",500,1000),("1000+",1000,999999)]
    pcolors = ["#10b981","#f59e0b","#3b82f6","#8b5cf6","#ec4899","#ef4444"]
    ps = [base_dff[(base_dff["成交均价"]>=lo)&(base_dff["成交均价"]<hi)]["销售额"].sum() for _,lo,hi in pbins]
    fp = go.Figure(go.Bar(x=[l for l,_,_ in pbins], y=[p/1e8 for p in ps], marker_color=pcolors, text=[f"{p/1e8:.1f}亿" for p in ps], textposition="outside"))
    fp.update_layout(title="💰 价格区间", yaxis_title="亿元", height=200, margin=dict(l=40,r=40,t=40,b=50))
    
    store_agg = base_dff.groupby("宝贝店铺名称").agg({"销售额":"sum","销量":"sum","宝贝ID":"nunique"}).reset_index().sort_values("销售额",ascending=False).head(100)
    store_agg["排名"] = range(1,len(store_agg)+1)
    store_agg["销售额(亿)"] = (store_agg["销售额"]/1e8).round(3)
    store_agg["销量(万)"] = (store_agg["销量"]/1e4).round(1)
    store_agg = store_agg[["排名","宝贝店铺名称","销售额(亿)","销量(万)","宝贝ID"]]
    store_agg.columns = ["排名","店铺名称","销售额(亿)","销量(万)","商品数"]
    
    prod_agg = base_dff.groupby(["宝贝名称","品牌"]).agg({"销售额":"sum","销量":"sum"}).reset_index().sort_values("销售额",ascending=False).head(100)
    prod_agg["排名"] = range(1,len(prod_agg)+1)
    prod_agg["销售额(万)"] = (prod_agg["销售额"]/1e4).round(1)
    prod_agg = prod_agg[["排名","宝贝名称","品牌","销售额(万)","销量"]]
    prod_agg.columns = ["排名","商品名称","品牌","销售额(万)","销量(件)"]
    
    return [{"display":"block","background":"#f0fdf4","padding":"15px","borderRadius":"12px"}, f"🔍 {title} 详细分析", fm, fp, make_table(store_agg,["排名","店铺名称","销售额(亿)","销量(万)","商品数"]), make_table(prod_agg,["排名","商品名称","品牌","销售额(万)","销量(件)"])]

if __name__ == "__main__":
    print("\n🚀 情报通 2025 V9\n📱 http://127.0.0.1:8050\n")
    app.run(debug=False, host="127.0.0.1", port=8050)
