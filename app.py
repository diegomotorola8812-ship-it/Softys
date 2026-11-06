from pathlib import Path
from html import escape
import re
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from analisis import (
    DIMS, FILES, norm, sku_key, canonical, source_path, read_sources, build_master, enrich,
    load_weights, select, nsg_result, nsg_alerts, peg_result, category_alerts,
    lin_result, binary_result, pdv_alerts, coverage, cover_stats, aggregate, number,
)

BASE=Path(__file__).resolve().parent
LOGO=BASE/'assets_softys_logo.png'
COLORS=['#0773A5','#2D4159','#65C5DD','#7BBE67','#F2B134','#D66565']
MONTHS=['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
st.set_page_config(page_title='SOFTYS · Alertas de ejecución',page_icon=str(LOGO) if LOGO.exists() else '📊',layout='wide')
st.markdown('''<style>
.block-container{max-width:1600px;padding:2rem 2.2rem 4rem}h1,h2,h3{letter-spacing:-.025em;color:#2d4159}
[data-testid="stMetric"]{padding:16px;background:#fff;border:1px solid #dfe8f1;border-top:3px solid #00a7bb;border-radius:10px}
[data-testid="stMetricLabel"]{color:#52718d}[data-testid="stMetricValue"]{color:#2d4159;font-weight:700}
.hero{background:#2d4159;border-radius:15px;padding:27px 30px;color:white;margin-bottom:22px;border-left:7px solid #65c5dd}
.hero h1{color:white;font-size:32px;margin:7px 0}.hero p{color:#d9f2f7;margin:4px 0}.eyebrow{font-size:12px;letter-spacing:.16em;color:#65c5dd;font-weight:700}
.analysis{background:#eaf3f7;border-left:4px solid #0773a5;padding:17px 21px;border-radius:0 9px 9px 0;margin:18px 0;color:#2d4159;line-height:1.6}
.region{border-radius:13px;background:#225582;color:white;padding:20px;margin:8px 0 12px;min-height:190px}
.region h3{color:#75e3e4;font-size:18px;margin:0 0 10px}.region .big{font-size:34px;font-weight:750}.region .sub{font-size:13px;color:#d5edf7}
.region .rates{color:#d2e86e;margin:8px 0;font-weight:650}.region .channels{font-size:13px;border-top:1px dotted #a4cada;padding-top:11px;line-height:1.9}
.national{background:#1b456c;border-radius:13px;color:white;padding:22px;margin:8px 0 15px}.national .big{font-size:42px;color:#c6dc56;font-weight:750}
.alert-card{background:#fff;border:1px solid #e3eaf1;border-left:5px solid #d46565;border-radius:11px;padding:15px 16px;min-height:142px;box-shadow:0 4px 14px rgba(24,83,131,.06)}
.alert-card .tag{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#6d8294;font-weight:700}.alert-card .focus{font-size:16px;color:#183e62;font-weight:700;margin:7px 0}.alert-card .value{font-size:29px;color:#c54f55;font-weight:800}.alert-card .meta{font-size:12px;color:#668097;margin-top:4px}
[data-baseweb="tab-list"]{gap:7px;flex-wrap:wrap}[data-baseweb="tab"]{padding:8px 14px;background:#fff;border-radius:7px}
</style>''',unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def prepare(root,period,signature):
    data,issues=read_sources(Path(root),period)
    extras=[]
    base_path=BASE/'configuracion'/'BASE DE PDV.xlsx'
    extra_path=BASE/'configuracion'/'maestro_pdv.csv'
    if base_path.exists():extras.append(pd.read_excel(base_path))
    if extra_path.exists():extras.append(pd.read_csv(extra_path))
    extra=pd.concat(extras,ignore_index=True) if extras else None
    master,more=build_master(data,extra)
    data={k:enrich(v,master) for k,v in data.items()}
    w=load_weights(BASE,period)
    ns,ni=nsg_result(data['nsg']);na,unmatched=nsg_alerts(data['nsg'],w)
    pe,ped,pi=peg_result(data['peg'],w)
    li,lid,lmi=lin_result(data['lin'])
    po,poi=binary_result(data['pop'],'POP')
    pre,pri=binary_result(data['pre_validado'],'Resultado PRE')
    sod,si=binary_result(data['sod_validado'],'Resultado SOD')
    results={'NSG':ns,'PEG':pe,'LIN':li,'PRE':pre,'SOD':sod,'POP':po}
    alerts={'NSG':na,'PEG':category_alerts(ped,w,'PEG'),'LIN':category_alerts(lid,w,'LIN'),
            'PRE':pdv_alerts(pre,w,'PRE'),'SOD':pdv_alerts(sod,w,'SOD'),'POP':pdv_alerts(po,w,'POP')}
    # Apply each KPI's channel scope from the supplied weights.
    for k in results:
        if not results[k].empty:
            valid=results[k]['Canal'].isin(w['kpi'][k])
            if (~valid).any():issues.append(f'{k}: {(~valid).sum()} PDV fuera de canales con peso; no se incluyen en el cumplimiento.')
            results[k]=results[k][valid]
    return data,w,master,results,alerts,unmatched,issues+more+ni+pi+lmi+poi+pri+si

def pct(x):return 'Sin dato' if pd.isna(x) else f'{x*100:.1f}%'
def integer(x):return f'{x:,.0f}'.replace(',','.')
def analysis(text):st.markdown(f'<div class="analysis">{escape(text)}</div>',unsafe_allow_html=True)
def download(d,name,key):
    if not d.empty:st.download_button('Descargar detalle CSV',d.to_csv(index=False).encode('utf-8-sig'),name,'text/csv',key=key)
def table(d):st.dataframe(d,width='stretch',hide_index=True)

def draw(fig,key):
    fig.update_layout(font=dict(family='Arial',color='#24445e',size=12),paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',margin=dict(l=20,r=25,t=24,b=30),
        legend=dict(orientation='h',y=1.15,title_text=''),hoverlabel=dict(bgcolor='white'),
        colorway=COLORS)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor='#e4edf5',zeroline=False)
    st.plotly_chart(fig,width='stretch',key=key,config={'displaylogo':False})

def bars(d,x,y,key,color=None,percent=False,horizontal=False):
    if d.empty:st.info('No hay mediciones para estos filtros.');return
    kwargs=dict(data_frame=d,x=x,y=y,color=color,color_discrete_sequence=COLORS,
                barmode='group',text_auto='.1f' if percent else '.0f')
    if horizontal:kwargs['orientation']='h'
    f=px.bar(**kwargs)
    f.update_traces(textposition='outside',cliponaxis=False)
    if percent:
        axis='xaxis' if horizontal else 'yaxis'
        f.update_layout(**{axis:dict(range=[0,max(105,float(d[x if horizontal else y].max())*1.12)],ticksuffix='%')})
    f.update_layout(height=max(320,len(d)*27) if horizontal else 350)
    draw(f,key)

def alert_cards(d,measure,label,key):
    """Show the three highest-priority alerts as compact decision cards."""
    if d.empty:return
    top=d.head(3).reset_index(drop=True)
    cols=st.columns(len(top))
    for col,(_,row) in zip(cols,top.iterrows()):
        focus=' · '.join(str(row.get(c,'')) for c in ['Regional','Canal','Tipología'] if pd.notna(row.get(c,'')))
        item=escape(str(row.get(label,'Sin identificar')))[:58]
        value=row.get(measure,np.nan)
        value='Sin dato' if pd.isna(value) else f'{float(value):.1f}%'
        priority=row.get('Prioridad pp',np.nan)
        priority='Sin prioridad' if pd.isna(priority) else f'Prioridad {float(priority):.2f} pp'
        col.markdown(f'<div class="alert-card"><div class="tag">Foco prioritario</div><div class="focus">{item}</div><div class="value">{value}</div><div class="meta">{escape(focus)}<br>{priority}</div></div>',unsafe_allow_html=True)

def alert_heatmap(d,measure,key):
    if d.empty or not {'Regional','Tipología',measure}.issubset(d.columns):return
    heat=d.groupby(['Regional','Tipología'],dropna=False)[measure].mean().reset_index()
    if heat.empty:return
    fig=px.density_heatmap(heat,x='Tipología',y='Regional',z=measure,text_auto='.1f',
        color_continuous_scale=['#d46565','#e9a642','#8dbf38'],range_color=[0,100])
    fig.update_layout(height=300,coloraxis_colorbar=dict(title='%',ticksuffix='%'))
    draw(fig,key,)

def breakdown(result,key):
    if result.empty:st.info('Sin mediciones de cumplimiento disponibles.');return
    left,right=st.columns([1.25,1])
    with left:
        st.subheader('Cumplimiento por regional')
        bars(aggregate(result,['Regional']),'Regional','Cumplimiento (%)',key+'_reg',percent=True)
    with right:
        st.subheader('Canal y tipología')
        pivot=aggregate(result,['Canal','Tipología'])
        bars(pivot,'Canal','Cumplimiento (%)',key+'_can',color='Tipología',percent=True)
    with st.expander('Abrir detalle por PDV'):
        d=result.copy();d['Cumplimiento (%)']=d['Resultado']*100
        cols=DIMS+['ID PDV','PDV','Cumplimiento (%)','Visitas']
        table(d[cols].round(2));download(d[cols],f'{key}_pdv_{period}.csv',key+'_csv')

def summary_analysis(result,kpi):
    if result.empty:return 'No hay una base válida para calcular este indicador con la selección actual.'
    reg=aggregate(result,['Regional']).sort_values('Cumplimiento (%)')
    low=reg.iloc[0];overall=result['Resultado'].mean()*100
    return (f'{kpi} alcanza {overall:.1f}% en {result["ID PDV"].nunique():,} PDV evaluados. '
            f'{low["Regional"]} presenta el menor resultado de esta selección ({low["Cumplimiento (%)"]:.1f}%). '
            'Priorice la validación de las brechas con mayor impacto ponderado y coordine la revisión con el equipo de campo. '
            'Esta lectura describe el cierre; no implica crecimiento ni caída frente a otro mes.')

root=next((p for p in BASE.iterdir() if p.is_dir() and p.name.lower()=='datos'),BASE/'datos')
if not root.exists():st.error('No se encontró Datos. Conserve sus carpetas Datos/AAAA-MM junto a app.py.');st.stop()
periods=sorted(p.name for p in root.iterdir() if p.is_dir() and re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',p.name))
if not periods:st.info('Agregue los Excel a Datos/2026-10.');st.stop()
if LOGO.exists(): st.sidebar.image(str(LOGO),width=150)
st.sidebar.title('Informe de ejecución')
period=st.sidebar.selectbox('Cierre mensual',periods,index=periods.index('2026-10') if '2026-10' in periods else len(periods)-1)
if st.sidebar.button('Actualizar datos y pesos',width='stretch'):st.cache_data.clear();st.rerun()
files=list((root/period).glob('*'))+list((BASE/'configuracion').rglob('*'))
signature=tuple(sorted((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in files if p.is_file()))
try:
    with st.spinner('Preparando mediciones y alertas ponderadas…'):
        data,weights,master,results,alerts,unmatched,issues=prepare(str(root/period),period,signature)
except Exception as error:
    st.error(f'No se pudo preparar el informe: {error}')
    st.info('Verifique los nombres de archivos y copie también analisis.py y configuracion del paquete.');st.stop()
filters={}
for dim in DIMS:
    opts=sorted(set(master[dim].dropna())|set(v for d in data.values() if dim in d for v in d[dim].dropna().unique()))
    filters[dim]=st.sidebar.multiselect(dim,opts)
threshold=st.sidebar.slider('Alerta si cumplimiento es inferior a',0,100,80,format='%d%%')
st.sidebar.caption('Umbral operativo propuesto. Los pesos ordenan el impacto; el umbral define qué alertas se muestran.')
fr={k:select(v,filters) for k,v in results.items()}
fa={k:select(v,filters) for k,v in alerts.items()}
fd={k:select(v,filters) for k,v in data.items()}
# Comparable priorities within the filtered KPI population, retaining segment pp for traceability.
for k in ['NSG','PEG','LIN']:
    if not fa[k].empty:
        a=fa[k].copy()
        a['Brecha segmento pp']=a['Prioridad pp']
        denominator=fr[k]['ID PDV'].nunique() if not fr[k].empty else 0
        a['Prioridad pp']=a['Brecha']*a['Peso KPI']*100/denominator if denominator else np.nan
        fa[k]=a.sort_values('Prioridad pp',ascending=False)

cover=select(coverage(data['rutas']),filters)
stats=cover_stats(cover)
month_text=f'{MONTHS[int(period[5:])-1]} de {period[:4]}'
st.markdown(f'<div class="hero"><div class="eyebrow">SOFTYS · INFORME GERENCIAL</div><h1>Ejecución y oportunidades en punto de venta</h1><p>Cierre de {escape(month_text)} · Resultados, prioridades y acciones comerciales</p></div>',unsafe_allow_html=True)
st.caption('Vista filtrada' if any(filters.values()) else 'Vista nacional · todos los datos disponibles')
with st.sidebar.expander('Pesos usados y trazabilidad'):
    st.write('Archivo:',Path(weights['path']).name)
    st.write('Portafolio de vigencia:',', '.join(weights['v']))
    st.caption('Se usa la configuración más reciente no posterior al cierre; no se modifica la fecha de las mediciones.')
    wt=pd.DataFrame(weights['kpi']).T.mul(100).rename_axis('KPI').reset_index()
    table(wt)
    st.caption('Peso vacío = no aplica. No se normalizan ni inventan ponderaciones.')
with st.expander(f'Calidad y alcance de las fuentes · {len(issues)} observaciones'):
    st.caption('Los datos con fecha se limitan al mes seleccionado. Las fuentes sin fecha se asignan por carpeta.')
    for issue in issues:st.write('• '+issue)
    unknown=(master[DIMS]=='POR VALIDAR').any(axis=1).sum()
    st.write(f'{unknown} PDV tienen al menos una dimensión sin validar. No se asignan a un canal o tipología por su nombre.')
    table(pd.DataFrame([{'Fuente':name,'Estado':'Disponible' if source_path(root/period,name) is not None else 'No disponible / opcional' if key.endswith('validado') else 'No disponible'} for key,name in FILES.items()]))

labels=['Resumen gerencial','Cobertura y frecuencia','NSG','PEG','Lineamientos','Precios','SOD','POP']
tabs=st.tabs(labels)

with tabs[0]:
    st.header('Dónde concentrar la gestión comercial')
    cols=st.columns(4)
    cols[0].metric('Cobertura de PDV',pct(stats['Cobertura']))
    for col,key,label in zip(cols[1:],['NSG','PEG','LIN'],['NSG reportado','PEG calculado','Lineamientos']):
        col.metric(label,pct(fr[key]['Resultado'].mean()) if not fr[key].empty else 'Sin dato')
    st.caption('Cada KPI tiene su propia base de PDV. No se mezclan como FDE total. NSG usa el resultado reportado; sus alertas se ponderan con el archivo de configuración.')
    rows=[]
    for key in ['NSG','PEG','LIN']:
        d=aggregate(fr[key],['Regional'])
        if not d.empty:d['KPI']=key;rows.append(d)
    if rows:
        st.subheader('Lectura regional de los KPI')
        bars(pd.concat(rows),'Regional','Cumplimiento (%)','summary_kpi',color='KPI',percent=True)
    profile=fr['NSG'].groupby(['Canal','Tipología'],dropna=False)['ID PDV'].nunique().reset_index(name='PDV') if not fr['NSG'].empty else pd.DataFrame()
    if not profile.empty:
        st.subheader('Perfil de PDV evaluados')
        st.caption('La base de PDV aporta la segmentación comercial. Oro, Plata y Bronce se mantienen como tipologías para orientar la gestión.')
        left,right=st.columns([1.2,1])
        with left:
            fig=px.treemap(profile,path=['Canal','Tipología'],values='PDV',color='PDV',color_continuous_scale=['#d9eef2','#00a7bb','#185383'])
            fig.update_layout(height=360,margin=dict(l=5,r=5,t=10,b=5));draw(fig,'summary_profile')
        with right:
            table(profile.sort_values('PDV',ascending=False))
    overview=[]
    for key in ['NSG','PEG','LIN']:
        a=fa[key]
        if not a.empty:
            measure='Presencia (%)' if key=='NSG' else 'Cumplimiento (%)'
            a=a[(a[measure]<threshold)&a['Prioridad pp'].notna()]
            for _,r in a.head(3).iterrows():overview.append({'KPI':key,'Regional':r['Regional'],'Canal':r['Canal'],'Tipología':r['Tipología'],'Foco':r['Producto'] if key=='NSG' else r['Categoría'],'Prioridad (pp)':r['Prioridad pp']})
    if overview:
        st.subheader('Agenda de prioridades por KPI')
        table(pd.DataFrame(overview).round(3))
        st.caption('Prioridad estimada sobre la población filtrada de cada KPI: brecha × peso interno × peso KPI × participación de PDV. Los KPI tienen bases distintas; no sume sus filas como FDE nacional.')
    analysis(f'La cobertura alcanza {pct(stats["Cobertura"])} y la frecuencia {pct(stats["Frecuencia"])} sobre la programación. '+summary_analysis(fr['NSG'],'NSG'))
    st.info('Lectura de mercadeo: primero asegure visita efectiva y disponibilidad del portafolio de mayor peso; después revise espacio en góndola y ejecución por categoría. Las causas deben confirmarse en campo.')

with tabs[1]:
    st.header('Cobertura y frecuencia')
    st.caption('Distribución inspirada en el reporte de cobertura: total, mezcla de canales y bloques regionales. Las cifras corresponden al cierre seleccionado.')
    left,right=st.columns([.85,2.15])
    with left:
        st.markdown(f'<div class="national"><div>PDV PROGRAMADOS</div><div class="big">{integer(stats["Universo"])}</div><b>{"Selección actual" if any(filters.values()) else "Nacional"}</b><p>Cobertura: {pct(stats["Cobertura"])}<br>Frecuencia: {pct(stats["Frecuencia"])}</p></div>',unsafe_allow_html=True)
        mix=cover[cover['Programadas']>0].groupby('Canal')['ID PDV'].nunique().rename('PDV').reset_index()
        if not mix.empty:
            f=px.pie(mix,names='Canal',values='PDV',hole=.7,color_discrete_sequence=COLORS)
            f.update_traces(textinfo='percent',hovertemplate='%{label}: %{value} PDV (%{percent})<extra></extra>')
            f.update_layout(height=310,showlegend=True);draw(f,'cover_mix')
            table(mix)
    with right:
        regs=sorted(cover['Regional'].unique())
        for i in range(0,len(regs),2):
            cols=st.columns(2)
            for col,reg in zip(cols,regs[i:i+2]):
                d=cover[cover['Regional']==reg];s=cover_stats(d)
                mix=d[d['Programadas']>0].groupby('Canal')['ID PDV'].nunique()
                content=' · '.join(f'{escape(str(c))}: <b>{integer(n)}</b>' for c,n in mix.items())
                col.markdown(f'<div class="region"><h3>{escape(str(reg))}</h3><div class="big">{integer(s["Atendidos"])}</div><div class="sub">PDV atendidos de {integer(s["Universo"])} programados</div><div class="rates">Cobertura {pct(s["Cobertura"])} · Frecuencia {pct(s["Frecuencia"])}</div><div class="channels">{content}</div></div>',unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    a.metric('Visitas programadas',integer(stats['Programadas']));b.metric('Realizadas en ruta',integer(stats['Realizadas']))
    c.metric('Cobertura',pct(stats['Cobertura']));d.metric('Frecuencia',pct(stats['Frecuencia']))
    groups=[]
    for keys,g in cover.groupby(DIMS,dropna=False):
        s=cover_stats(g)
        groups.append(dict(zip(DIMS,keys),**{'PDV programados':s['Universo'],'PDV atendidos':s['Atendidos'],'Cobertura (%)':s['Cobertura']*100,'Frecuencia (%)':s['Frecuencia']*100}))
    detail=pd.DataFrame(groups)
    if not detail.empty:
        st.subheader('Cumplimiento por tipología')
        dimension=st.selectbox('Desglosar cumplimiento por',DIMS,key='cover_dimension')
        groups_chart=[]
        for label,g in cover.groupby(dimension):
            v=cover_stats(g)
            groups_chart.extend([{dimension:label,'Medida':'Cobertura','Cumplimiento (%)':v['Cobertura']*100},{dimension:label,'Medida':'Frecuencia','Cumplimiento (%)':v['Frecuencia']*100}])
        long=pd.DataFrame(groups_chart)
        bars(long,dimension,'Cumplimiento (%)','cover_detail',color='Medida',percent=True)
        table(detail.round(2))
    st.caption('Cobertura = PDV programados con al menos una visita realizada / PDV programados. Frecuencia = visitas realizadas en ruta / visitas programadas. Puede superar 100%. Extra ruta se excluye. Una fila por PDV tras sumar carga por personal; confirme si la exportación duplica visitas compartidas.')
    bad=cover[(cover['Programadas']>0)&(cover['Frecuencia']*100<threshold)].sort_values('Frecuencia')
    if not bad.empty:
        with st.expander('PDV con frecuencia por debajo del umbral'):
            table(bad);download(bad,f'frecuencia_{period}.csv','cover_csv')
    unclassified=cover[(cover[DIMS]=='POR VALIDAR').any(axis=1)]
    if len(unclassified):st.warning(f'{len(unclassified)} PDV tienen canal o tipología sin validar. Puede completar configuracion/maestro_pdv.csv; no se infieren Farmacias o Plazas a partir del nombre.')
    analysis(f'En esta selección se atendieron {integer(stats["Atendidos"])} de {integer(stats["Universo"])} PDV programados. La frecuencia fue {pct(stats["Frecuencia"])}. Revise primero los puntos sin atención y luego los que recibieron menos visitas de las programadas; una cobertura alta no garantiza que se cumpla toda la frecuencia.')

# NSG / PEG / LIN share the same hierarchy but preserve different source granularity.
for tab,key,title in [(tabs[2],'NSG','Nivel de servicio en góndola'),(tabs[3],'PEG','Participación en góndola'),(tabs[4],'LIN','Lineamientos de exhibición')]:
    with tab:
        st.header(title)
        result=fr[key]
        c1,c2,c3=st.columns(3)
        c1.metric('Cumplimiento',pct(result['Resultado'].mean()) if not result.empty else 'Sin dato')
        c2.metric('PDV evaluados',integer(result['ID PDV'].nunique()) if not result.empty else '0')
        c3.metric('Visitas válidas',integer(result['Visitas'].sum()) if not result.empty else '0')
        if key=='NSG':
            st.caption('Resultado NSG reportado por visita, promediado por PDV y después entre PDV. Ranking de productos recalculado con los pesos de configuración; no se sustituye silenciosamente el NSG reportado.')
        elif key=='PEG':
            st.caption('Participación real / mínimo por categoría, limitada a 100%; ponderada por categoría con el Excel de configuración. Solo visitas completas. No se promedian las filas de SKU.')
        else:st.caption('Resultado del índice de lineamiento por visita. Alertas por categoría: bloques de marca, no productos individuales. Pañaleras: pañales; otros canales: las tres categorías con igual peso según el ejemplo.')
        breakdown(result,key)
        analysis(summary_analysis(result,key))
        a=fa[key].copy()
        measure='Presencia (%)' if key=='NSG' else 'Cumplimiento (%)'
        label='Producto' if key=='NSG' else 'Categoría'
        if not a.empty:
            a=a[(a[measure]<threshold)&a['Prioridad pp'].notna()]
        st.subheader('Alertas por producto y regional' if key=='NSG' else 'Alertas por categoría y regional')
        if a.empty:st.info('Sin alertas ponderadas para el umbral y la base disponible. Consulte la cobertura de pesos antes de interpretar este resultado.')
        else:
            top=a.head(12).copy()
            top['Foco']=top['Regional']+' · '+top['Canal']+' · '+top['Tipología']+' · '+top[label].str.slice(0,48)
            alert_cards(a,measure,label,key+'_cards')
            st.subheader('Mapa de brechas por regional y tipología')
            alert_heatmap(a,measure,key+'_heatmap')
            st.subheader('Ranking de prioridades')
            bars(top.sort_values('Prioridad pp'),'Prioridad pp','Foco',key+'_alerts',horizontal=True)
            st.caption('Prioridad (pp estimados de la base filtrada): suma de brechas medias por PDV × peso interno × peso KPI / PDV evaluados del KPI. Se muestran también los pp del segmento; no equivale a ventas perdidas.')
            cols=DIMS+[label,measure,'Peso SKU (%)' if key=='NSG' else 'Peso categoría (%)','PDV_evaluados','Base PDV','Brecha segmento pp','Prioridad pp']
            table(a[cols].round(3));download(a,f'alertas_{key}_{period}.csv',key+'_alerts_csv')
            first=a.iloc[0]
            analysis(f'Primer foco de revisión: {first[label]} en {first["Regional"]}, {first["Canal"]}, {first["Tipología"]}. El resultado es {first[measure]:.1f}% y la prioridad ponderada es {first["Prioridad pp"]:.3f} pp estimados de la base filtrada del KPI. '+('Valide inventario y reposición del portafolio infaltable.' if key=='NSG' else 'Revise la categoría con el equipo comercial; esta fuente no identifica el SKU responsable.'))
        if key=='NSG':
            missing=select(unmatched,filters)
            st.caption(f'{len(missing)} combinaciones de producto sin peso válido o sin disponibilidad válida para la prioridad; no se usa un peso inventado.')
            if not missing.empty:
                with st.expander('Productos pendientes de homologar con los pesos'):
                    table(missing);download(missing,f'productos_sin_peso_{period}.csv','unmatched')
        if key=='PEG':
            st.info('La fuente mide PH, pañales y toallas de cocina. No permite atribuir incumplimiento PEG a un SKU. Los pesos de NSG no se trasladan a PEG.')
        if key=='LIN':st.info('No hay evaluación de lineamiento por SKU en los archivos recibidos. Las alertas se presentan por categoría y por PDV.')

with tabs[5]:
    st.header('Precios y marcación')
    pre=fr['PRE'];raw=fd['precios']
    a,b,c=st.columns(3)
    a.metric('Cumplimiento PRE',pct(pre['Resultado'].mean()) if not pre.empty else 'Sin fuente')
    b.metric('Peso PRE · Superetes',pct(weights['kpi']['PRE'].get('SUPERETES',np.nan)))
    c.metric('Peso PRE · Cadenas',pct(weights['kpi']['PRE'].get('CADENAS',np.nan)))
    if pre.empty:
        st.warning('El archivo actual contiene precios propios y de competencia; no acredita precio correcto, visible y accesible. No se presenta un cumplimiento PRE artificial.')
        analysis('La lectura de precios permite orientar revisión de posicionamiento, pero no reemplaza la auditoría de marcación. Complete la fuente de cumplimiento por visita para priorizar brechas PRE con su peso.')
    else:
        breakdown(pre,'PRE');analysis(summary_analysis(pre,'PRE'))
        a=fa['PRE'];a=a[a['Cumplimiento (%)']<threshold]
        table(a.round(3));download(a,f'alertas_PRE_{period}.csv','pre_csv')
    if not raw.empty and 'Precio Propio' in raw:
        raw=raw.copy();raw['Precio Propio']=number(raw['Precio Propio'])
        raw=raw[raw['Precio Propio'].gt(0)&raw['Nombre de producto'].notna()]
        st.subheader('Precios propios observados · diagnóstico complementario')
        st.caption('Mediana de precios registrados por producto. No es porcentaje de cumplimiento ni comparación entre presentaciones equivalentes.')
        if not raw.empty:
            top=raw.groupby('Nombre de producto')['Precio Propio'].median().nlargest(12).reset_index()
            bars(top.sort_values('Precio Propio'),'Precio Propio','Nombre de producto','prices',horizontal=True)
            with st.expander('Detalle de observaciones de precio'):
                cols=[c for c in DIMS+['Fecha','PDV','Nombre de producto','Precio Propio','Producto competencia','Precio Competencia'] if c in raw]
                table(raw[cols].head(500));download(raw[cols],f'precios_observados_{period}.csv','prices_csv')
        else:st.info('No hay precios propios positivos con producto identificado en la selección.')
    with st.expander('Cómo habilitar el cumplimiento PRE'):
        st.write('Agregue Cumplimiento PRE por visita.csv al mes. Columnas: Fecha, ID PDV, Resultado PRE. Resultado PRE es el porcentaje como fracción 0–1 calculado sobre productos presentes con marcación correcta, visible y accesible. Una fila por ID y fecha. Plantilla vacía incluida en plantillas.')
        st.caption('La plantilla por visita permite alertas por PDV; para alertas de producto se requiere una fuente de auditoría por SKU.')

with tabs[6]:
    st.header('SOD · Exhibiciones adicionales')
    result=fr['SOD'];d=fd['sod'].copy()
    a,b,c=st.columns(3)
    a.metric('Cumplimiento SOD',pct(result['Resultado'].mean()) if not result.empty else 'Sin denominador')
    b.metric('Peso SOD · Superetes',pct(weights['kpi']['SOD'].get('SUPERETES',np.nan)))
    c.metric('Peso SOD · Cadenas',pct(weights['kpi']['SOD'].get('CADENAS',np.nan)))
    if result.empty:
        st.warning('La fuente SDO tiene cantidades por PDV/tipo de exhibición y no tiene fecha de visita. No permite medir el porcentaje de visitas que cumplen ni identificar PDV sin exhibición.')
        analysis('Use la distribución de registros como inventario de actividad observada. Para orientar cierres de brechas se requiere una base con visitas evaluadas y resultados 0/1, incluidos los ceros. Las cantidades observadas no representan cumplimiento.')
    else:
        breakdown(result,'SOD');analysis(summary_analysis(result,'SOD'))
        a=fa['SOD'];a=a[a['Cumplimiento (%)']<threshold]
        table(a.round(3));download(a,f'alertas_SOD_{period}.csv','sod_csv')
    if not d.empty:
        st.subheader('Distribución de registros de exhibición')
        st.caption('Se cuentan filas del exportado por tipo; no son visitas únicas, ni se suman valores repetidos de SOD como exhibiciones únicas.')
        group=d.groupby(['Regional','TipoExhibicion']).size().rename('Registros').reset_index()
        bars(group,'Regional','Registros','sod_records',color='TipoExhibicion')
        with st.expander('Detalle recibido y coincidencias por nombre'):
            table(d);download(d,f'exhibiciones_observadas_{period}.csv','sod_observed')
        unknown=d['ID PDV'].isna().sum() if 'ID PDV' in d else len(d)
        if unknown:st.caption(f'{unknown} registros sin cruce único con el maestro por nombre exacto normalizado; no se asignan arbitrariamente.')
    with st.expander('Cómo habilitar el cumplimiento SOD'):
        st.write('Agregue Cumplimiento SOD por visita.csv con Fecha, ID PDV, Resultado SOD (0/1: al menos una exhibición adicional). Incluya visitas sin exhibición con resultado 0. Confirme que SOD corresponde a EXH de la metodología antes de usarlo como FDE.')

with tabs[7]:
    st.header('POP · Material en punto de venta')
    result=fr['POP']
    a,b,c=st.columns(3)
    a.metric('Cumplimiento POP',pct(result['Resultado'].mean()) if not result.empty else 'Sin dato')
    b.metric('PDV evaluados',integer(result['ID PDV'].nunique()) if not result.empty else '0')
    c.metric('Peso · Pañaleras',pct(weights['kpi']['POP'].get('PAÑALERAS',np.nan)))
    breakdown(result,'POP');analysis(summary_analysis(result,'POP'))
    st.caption('POP: al menos una pieza de material en la visita. Peso del Excel: Pañaleras 7%, Cadenas 5%; Superetes no aplica. No se identifican productos individuales.')
    a=fa['POP']
    if not a.empty:
        a=a[(a['Cumplimiento (%)']<threshold)&a['Prioridad pp'].notna()]
    st.subheader('Alertas por PDV y regional')
    if a.empty:st.info('Sin alertas en la base disponible para esta selección.')
    else:
        top=a.head(12).copy();top['Foco']=top['Regional']+' · '+top['PDV'].str.slice(0,45)
        bars(top.sort_values('Prioridad pp'),'Prioridad pp','Foco','pop_alerts',horizontal=True)
        table(a[DIMS+['PDV','ID PDV','Cumplimiento (%)','Visitas','Prioridad pp']].round(3))
        download(a,f'alertas_POP_{period}.csv','pop_alerts_csv')
        st.caption('Prioridad por PDV = brecha del PDV × peso POP del canal, en pp; no es una pérdida regional agregada.')

st.divider()
with st.expander('Metodología, límites y actualización mensual'):
    st.markdown('''
- **General a detalle:** promedio de visitas por PDV y después promedio simple de PDV. Cada KPI informa su población.
- **Pesos:** el archivo de configuración se lee al ejecutar. Se aplica la fila del canal y los pesos internos propios de cada KPI. No se copian los pesos de productos NSG a otros indicadores.
- **Prioridad:** combina brecha y peso, no es un pronóstico de ventas ni una causa demostrada. El umbral del semáforo es configurable.
- **NSG:** porcentaje reportado en la exportación. Las alertas por SKU usan disponibilidad y peso configurado. Productos sin coincidencia exacta normalizada quedan en pendientes, nunca reciben peso cero.
- **PEG:** mínimos y ponderaciones por categoría del Excel; visitas sin categorías requeridas válidas quedan excluidas. Una categoría con participación superior al mínimo aporta como máximo 100%.
- **Lineamientos:** se usa el índice reportado. La prioridad por categoría usa ponderación igual del ejemplo (solo pañales en pañaleras); valide si su política por categoría es distinta.
- **Precios y SOD:** vistas de diagnóstico con las fuentes actuales; cumplimiento se habilita únicamente con fuentes adicionales válidas.
- **Histórico:** agregue Datos/AAAA-MM. Los archivos sin fecha pertenecen al mes de la carpeta. Para otra vigencia de pesos coloque el Excel en configuracion/AAAA-MM con el mismo nombre; conserve los anteriores.
- **Maestro opcional:** configuracion/maestro_pdv.csv agrega ID, nombre, regional, canal y tipología faltantes. Conflictos no se resuelven adivinando.
- **FDE total:** no se calcula mientras falten indicadores y validación de reglas. No se fabrica una tendencia mensual con un solo cierre.
''')
