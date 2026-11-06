"""Cálculos trazables del informe. No depende de Streamlit ni cambia los Excel."""
from pathlib import Path
import re
import unicodedata
import numpy as np
import pandas as pd

DIMS = ['Regional', 'Canal', 'Tipología']
FILES = {
    'rutas':'VISITAS PROGRAMADAS EN EL MES POR PUNTO DE VENTA.xlsx',
    'nsg':'Detalle de presencia de NSG Por Visita.xlsx',
    'presencia':'Presencia NSG por SKU.xlsx',
    'peg':'Detalle de Participacion Por Visita.xlsx',
    'lin':'Detalle Indicador Lineamiento Por Visita.xlsx',
    'precios':'Detalle de Precios Día a Día.xlsx',
    'sod':'Detalle SDO por PDV.xlsx',
    'pop':'Detalle POP por PDV Por Visita.xlsx',
    'segmentos':'Detalle PEG por segmentocategoria.xlsx',
    'novedades':'PUNTOS DE VENTA CON NOVEDAD.xlsx',
    'pre_validado':'Cumplimiento PRE por visita.csv',
    'sod_validado':'Cumplimiento SOD por visita.csv',
}

def norm(x):
    if pd.isna(x): return ''
    return re.sub(r'\s+', ' ', ''.join(c for c in unicodedata.normalize('NFKD', str(x).strip().upper()) if not unicodedata.combining(c)))

def sku_key(x):
    return re.sub(r'[^A-Z0-9]', '', norm(x))

def canal(x):
    x=norm(x)
    return {'SMI':'SUPERETES','SUPERETE':'SUPERETES','SUPERETES':'SUPERETES',
            'PANALERA':'PAÑALERAS','PANALERAS':'PAÑALERAS','PN':'PAÑALERAS',
            'CD':'CADENAS','MODERNO':'CADENAS','CADENAS':'CADENAS',
            'FM':'FARMACIAS','FARMACIA':'FARMACIAS','PZ':'PLAZAS'}.get(x,x)

def categoria(x):
    x=norm(x)
    if 'HIGIEN' in x or x=='PH': return 'PAPEL HIGIÉNICO'
    if 'TOALL' in x or x=='TC': return 'TOALLAS DE COCINA'
    if 'PANAL' in x or x in ['PN','PÑ']: return 'PAÑALES'
    return x

def number(x):return pd.to_numeric(x,errors='coerce')

def source_path(folder,name):
    """Resolve the canonical export name, allowing a source-system prefix."""
    folder=Path(folder)
    exact=folder/name
    if exact.exists(): return exact
    candidates=sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.name.casefold().endswith(name.casefold())
    )
    return candidates[0] if candidates else None

def canonical(d):
    d=d.copy();d.columns=[str(c).strip() for c in d.columns]
    rename={'FECHA':'Fecha','Fecha de visita':'Fecha','REGIONAL':'Regional','CANAL':'Canal',
            'CLASIFICACIÓN':'Tipología','Clasificacion':'Tipología','Clasificación':'Tipología',
            'ID Punto Venta':'ID PDV','ID PUNTO DE VENTA':'ID PDV','Id PDV':'ID PDV','Cód. PDV':'ID PDV',
            'Punto Venta':'PDV','PUNTO VENTA':'PDV','Punto de Venta':'PDV','NOMBRE PDV':'PDV','Nombre PDV':'PDV','PUNTO DE VENTA':'PDV',
            'DIVISIÓN':'Regional','DIVISI�N':'Regional','NIVEL 3':'Tipología','NIVEL 4':'Canal'}
    d=d.rename(columns=rename)
    if 'ID PDV' in d:
        d['ID PDV']=number(d['ID PDV']).astype('Int64').astype('string')
    for c in ['Regional','Tipología']:
        if c in d:d[c]=d[c].map(norm).replace('',pd.NA)
    if 'Canal' in d:d['Canal']=d['Canal'].map(canal).replace('',pd.NA)
    if 'PDV' in d:d['Nombre clave']=d['PDV'].map(sku_key)
    return d

def read_sources(folder, period):
    data={};issues=[]
    for key,name in FILES.items():
        p=source_path(folder,name)
        if p is None:data[key]=pd.DataFrame();continue
        try:
            d=canonical(pd.read_csv(p) if p.suffix=='.csv' else pd.read_excel(p))
            # Ignore entirely empty export separators before counting invalid records.
            d=d.dropna(how='all')
            if key in ['pre_validado','sod_validado']:
                required={'Fecha','ID PDV','Resultado PRE' if key=='pre_validado' else 'Resultado SOD'}
                if not required.issubset(d):
                    raise ValueError('Faltan columnas: '+', '.join(sorted(required-set(d.columns))))
            if 'Fecha' in d:
                dates=pd.to_datetime(d['Fecha'],errors='coerce')
                valid=dates.dt.strftime('%Y-%m').eq(period)
                if (~valid).any():issues.append(f'{name}: {(~valid).sum()} filas sin fecha del cierre excluidas (incluye pies de exportación).')
                d=d[valid].copy();d['Fecha']=dates[valid].dt.normalize()
            if 'ID PDV' in d:
                bad=d['ID PDV'].isna()
                if bad.any():issues.append(f'{name}: {bad.sum()} filas sin ID excluidas.')
                d=d[~bad].copy()
            if 'PDV' in d and 'ID PDV' not in d:
                d=d[d['PDV'].notna()].copy()
            data[key]=d
        except Exception as e:
            issues.append(f'{name}: no se pudo leer: {e}');data[key]=pd.DataFrame()
    return data,issues

def build_master(data, extra=None):
    parts=[d[['ID PDV']+[c for c in DIMS+['PDV','Nombre clave'] if c in d]].copy()
           for d in data.values() if not d.empty and 'ID PDV' in d]
    if extra is not None and not extra.empty:parts.append(canonical(extra))
    if not parts:return pd.DataFrame(columns=['ID PDV']+DIMS+['PDV']),[]
    all_rows=pd.concat(parts,ignore_index=True); master=pd.DataFrame({'ID PDV':all_rows['ID PDV'].dropna().unique()});issues=[]
    for c in DIMS+['PDV']:
        if c not in all_rows:master[c]=pd.NA;continue
        series=all_rows[['ID PDV',c]].dropna()
        if c=='PDV':
            vals=series.drop_duplicates('ID PDV').set_index('ID PDV')[c]
        else:
            counts=series.groupby('ID PDV')[c].nunique();conflicts=counts[counts>1]
            if len(conflicts):issues.append(f'Maestro: {len(conflicts)} ID con {c} en conflicto; quedan POR VALIDAR.')
            vals=series[~series['ID PDV'].isin(conflicts.index)].drop_duplicates('ID PDV').set_index('ID PDV')[c]
        master[c]=master['ID PDV'].map(vals)
    master['Nombre clave']=master['PDV'].map(sku_key)
    master[DIMS]=master[DIMS].fillna('POR VALIDAR')
    return master,issues

def enrich(d,master):
    if d.empty:return d.copy()
    d=d.copy()
    if 'ID PDV' not in d and 'Nombre clave' in d:
        m=master[master['Nombre clave'].ne('')].copy()
        unique=m.groupby('Nombre clave')['ID PDV'].nunique()
        m=m[m['Nombre clave'].isin(unique[unique==1].index)].drop_duplicates('Nombre clave')
        d=d.merge(m[['Nombre clave','ID PDV']],on='Nombre clave',how='left',validate='many_to_one')
    if 'ID PDV' in d:
        for c in DIMS+['PDV']:
            mapped=d['ID PDV'].map(master.set_index('ID PDV')[c])
            if c not in d:d[c]=mapped
            else:d[c]=d[c].fillna(mapped)
    for c in DIMS:
        if c not in d:d[c]='POR VALIDAR'
        d[c]=d[c].fillna('POR VALIDAR')
    return d

def load_weights(base,period):
    folder=Path(base)/'configuracion'
    monthly=folder/period/'MEDICIÓN ACTUAL FDE 2026.xlsx'
    p=monthly if monthly.exists() else folder/'MEDICIÓN ACTUAL FDE 2026.xlsx'
    if not p.exists():raise FileNotFoundError(f'Falta {p}')
    book=pd.ExcelFile(p)
    s=next(s for s in book.sheet_names if s.strip()=='RESUMEN CALCULO')
    raw=pd.read_excel(book,sheet_name=s,header=None)
    kpis={};mins={};cats={}
    channel_cols={i:canal(raw.iloc[3,i]) for i in range(1,4)}
    for r in range(4,10):
        key=norm(raw.iloc[r,0]);kpis[key]={channel_cols[i]:float(raw.iloc[r,i]) for i in range(1,4) if pd.notna(raw.iloc[r,i])}
    for ch in channel_cols.values():
        values=[d[ch] for d in kpis.values() if ch in d]
        if not all(0<=x<=1 for x in values) or not np.isclose(sum(values),1,atol=.002):
            raise ValueError(f'Pesos KPI inválidos para {ch}: deben ser fracciones 0–1 y sumar 100%.')
    # Locate section headers rather than assume row offsets for PEG tables.
    for target,dest in [('MINIMO REQUERIDO POR CATEGORIA Y CANAL',mins),('PESO POR CATEGORIA Y CANAL',cats)]:
        matches=raw.index[raw[0].map(norm).eq(target)]
        if not len(matches):raise ValueError(f'No se encontró {target}')
        start=int(matches[0])+2
        for r in range(start,start+3):
            cat=categoria(raw.iloc[r,0])
            for i in range(1,4):
                if pd.notna(raw.iloc[r,i]):dest[(channel_cols[i],cat)]=float(raw.iloc[r,i])
    port=pd.read_excel(book,sheet_name='INFALTABLES 26')
    port=port.rename(columns={'SubCanal':'Canal','Clasificacion':'Tipología','Sku':'Producto','Peso %':'Peso SKU'})
    port=canonical(port)
    port['Producto clave']=port['Producto'].map(sku_key)
    port['Vigencia']=pd.to_datetime(dict(year=number(port['Año']),month=number(port['Mes']),day=1),errors='coerce')
    port=port[port['Vigencia']<=pd.Timestamp(period+'-01')].copy()
    keys=DIMS+['Producto clave']
    if not port.empty:
        latest=port.groupby(keys,dropna=False)['Vigencia'].transform('max')
        port=port[port['Vigencia'].eq(latest)]
        # Chain can be dropped only when all candidate chains have the same weight.
        check=port.groupby(keys,dropna=False)['Peso SKU'].nunique()
        ambiguous=check[check>1].reset_index()[keys]
        if not ambiguous.empty:
            port=port.merge(ambiguous.assign(Ambigua=True),on=keys,how='left')
            port=port[port['Ambigua'].isna()]
        port=port.drop_duplicates(keys)
    return {'kpi':kpis,'min':mins,'cat':cats,'port':port,'path':str(p),'v':sorted(port['Vigencia'].dt.strftime('%Y-%m').dropna().unique())}

def select(d,filters):
    out=d.copy()
    for c,values in filters.items():
        if values and c in out:out=out[out[c].isin(values)]
    return out

def unique_visits(d,columns):
    """Collapse exact duplicate measurements; exclude conflicting duplicates."""
    if d.empty:return d.copy(),0
    d=d.drop_duplicates(['ID PDV','Fecha']+columns)
    conflict=d.groupby(['ID PDV','Fecha'],dropna=False).size()
    bad=conflict[conflict>1].reset_index()[['ID PDV','Fecha']]
    if bad.empty:return d,0
    d=d.merge(bad.assign(_bad=1),on=['ID PDV','Fecha'],how='left')
    return d[d['_bad'].isna()].drop(columns='_bad'),len(bad)

def per_pdv(visits):
    if visits.empty:return pd.DataFrame(columns=['ID PDV']+DIMS+['PDV','Resultado','Visitas'])
    v=visits.copy();v['Resultado']=number(v['Resultado'])
    v=v[v['Resultado'].between(0,1)]
    return v.groupby(['ID PDV']+DIMS,dropna=False).agg(Resultado=('Resultado','mean'),Visitas=('Resultado','size'),PDV=('PDV','first')).reset_index()

def nsg_result(d):
    if d.empty:return pd.DataFrame(),['Sin fuente NSG.']
    v=d[['ID PDV','Fecha']+DIMS+['PDV','% Real NSG']].rename(columns={'% Real NSG':'Resultado'})
    v,bad=unique_visits(v,['Resultado'])
    return per_pdv(v),[f'{bad} visitas NSG con resultados contradictorios excluidas.'] if bad else []

def nsg_alerts(d,weights):
    if d.empty:return pd.DataFrame(),pd.DataFrame()
    d=d.copy();d['Producto clave']=d['Sku Infaltable'].map(sku_key)
    d=d.rename(columns={'Sku Infaltable':'Producto','Peso Sku':'Peso exportado'})
    p=weights['port'];keys=DIMS+['Producto clave']
    d=d.merge(p[keys+['Peso SKU']].rename(columns={'Peso SKU':'Peso configuración'}),on=keys,how='left',validate='many_to_one')
    # Configuration is authoritative; exported weights are shown for comparison, not silently used.
    d['Disponibilidad']=number(d['Disponibilidad']);d['Peso configuración']=number(d['Peso configuración'])
    valid=d['Disponibilidad'].isin([0,1]) & d['Peso configuración'].between(0,1)
    unmatched=d[~valid][DIMS+['Producto','Peso exportado']].drop_duplicates()
    t=d[valid].copy()
    t=t.drop_duplicates(['ID PDV','Fecha','Producto clave','Disponibilidad'])
    conflict=t.groupby(['ID PDV','Fecha','Producto clave'])['Disponibilidad'].transform('nunique').gt(1)
    t=t[~conflict]
    if t.empty:return pd.DataFrame(),unmatched
    t['Brecha SKU']= (1-t['Disponibilidad'])*t['Peso configuración']
    psku=t.groupby(['ID PDV']+DIMS+['Producto'],dropna=False).agg(
        Presencia=('Disponibilidad','mean'),Brecha=('Brecha SKU','mean'),Peso=('Peso configuración','first'),
        Peso_exportado=('Peso exportado','first')).reset_index()
    alerts=psku.groupby(DIMS+['Producto'],dropna=False).agg(
        Presencia=('Presencia','mean'),Brecha=('Brecha','sum'),Peso=('Peso','first'),PDV_evaluados=('ID PDV','nunique'),
        Peso_exportado=('Peso_exportado','first')).reset_index()
    denominators=d.groupby(DIMS,dropna=False)['ID PDV'].nunique().rename('Base PDV').reset_index()
    alerts=alerts.merge(denominators,on=DIMS,validate='many_to_one')
    alerts['Peso KPI']=alerts['Canal'].map(weights['kpi']['NSG'])
    alerts['Prioridad pp']=alerts['Brecha']/alerts['Base PDV']*alerts['Peso KPI']*100
    alerts['Presencia (%)']=alerts['Presencia']*100
    alerts['Peso SKU (%)']=alerts['Peso']*100
    alerts['Peso exportado (%)']=number(alerts['Peso_exportado'])*100
    return alerts.sort_values('Prioridad pp',ascending=False),unmatched

def peg_result(d,weights):
    if d.empty:return pd.DataFrame(),pd.DataFrame(),[]
    pairs={'PAPEL HIGIÉNICO':('Cms Propios Ph','Cms Total Ph'),
           'PAÑALES':('Cms Propios Pñ','Cms Total Pñ'),
           'TOALLAS DE COCINA':('Cms Propios toallas','Cms Total Toallas')}
    v,bad=unique_visits(d,list(sum((list(x) for x in pairs.values()),[])))
    pieces=[]
    for cat,(own,total) in pairs.items():
        t=v[['ID PDV','Fecha']+DIMS+['PDV']].copy();t['Categoría']=cat
        t['Participación']=number(v[own])/number(v[total]).where(number(v[total])>0)
        t['Mínimo']=t['Canal'].map(lambda c:weights['min'].get((c,cat),np.nan))
        t['Peso categoría']=t['Canal'].map(lambda c:weights['cat'].get((c,cat),np.nan))
        t['Resultado categoría']=(t['Participación']/t['Mínimo']).clip(upper=1)
        t['Válido']=t['Participación'].between(0,1)&t['Resultado categoría'].between(0,1)
        t=t[t['Peso categoría'].notna()]
        pieces.append(t)
    detail=pd.concat(pieces,ignore_index=True)
    detail['Aporte']=detail['Resultado categoría']*detail['Peso categoría']
    summary=detail.groupby(['ID PDV','Fecha']+DIMS+['PDV'],dropna=False).agg(
        Resultado=('Aporte','sum'),Completo=('Válido','all'),Peso=('Peso categoría','sum')).reset_index()
    summary['Completo']=summary['Completo']&np.isclose(summary['Peso'],1,atol=.002)
    excluded=int((~summary['Completo']).sum())
    complete_keys=summary.loc[summary['Completo'],['ID PDV','Fecha']]
    detail=detail.merge(complete_keys,on=['ID PDV','Fecha'],how='inner',validate='many_to_one')
    return per_pdv(summary[summary['Completo']]),detail,[f'PEG: {excluded} visitas incompletas y {bad} visitas contradictorias excluidas.']

def category_alerts(detail,weights,kpi):
    if detail.empty:return pd.DataFrame()
    v=detail[detail['Válido']].copy()
    v['Brecha']=(1-v['Resultado categoría'])*v['Peso categoría']
    by=v.groupby(['ID PDV']+DIMS+['Categoría'],dropna=False).agg(Resultado=('Resultado categoría','mean'),Brecha=('Brecha','mean'),Peso=('Peso categoría','first')).reset_index()
    a=by.groupby(DIMS+['Categoría'],dropna=False).agg(Resultado=('Resultado','mean'),Brecha=('Brecha','sum'),Peso=('Peso','first'),PDV_evaluados=('ID PDV','nunique')).reset_index()
    base=by.groupby(DIMS,dropna=False)['ID PDV'].nunique().rename('Base PDV').reset_index()
    a=a.merge(base,on=DIMS);a['Peso KPI']=a['Canal'].map(weights['kpi'][kpi])
    a['Prioridad pp']=a['Brecha']/a['Base PDV']*a['Peso KPI']*100
    a['Cumplimiento (%)']=a['Resultado']*100;a['Peso categoría (%)']=a['Peso']*100
    return a.sort_values('Prioridad pp',ascending=False)

def lin_result(d):
    if d.empty:return pd.DataFrame(),pd.DataFrame(),[]
    v,bad=unique_visits(d,['PH','PÑ','TC','RESULTADO INDEX'])
    result=per_pdv(v.rename(columns={'RESULTADO INDEX':'Resultado'}))
    pieces=[]
    for col,cat in [('PH','PAPEL HIGIÉNICO'),('PÑ','PAÑALES'),('TC','TOALLAS DE COCINA')]:
        t=v[['ID PDV','Fecha']+DIMS+['PDV']].copy();t['Categoría']=cat
        t['Resultado categoría']=number(v[col]);t['Válido']=t['Resultado categoría'].isin([0,1])
        # Equal category shares as defined in the example. Not NSG SKU weights.
        t['Peso categoría']=np.where(t['Canal'].eq('PAÑALERAS'), 1.0 if cat=='PAÑALES' else 0.0, 1/3)
        t=t[t['Peso categoría']>0]
        pieces.append(t)
    return result,pd.concat(pieces,ignore_index=True),([f'LIN: {bad} visitas contradictorias excluidas.'] if bad else [])

def binary_result(d,column):
    if d.empty:return pd.DataFrame(),[]
    v=d.copy();v['Resultado']=number(v[column]);v=v[v['Resultado'].between(0,1)]
    v,bad=unique_visits(v,['Resultado'])
    return per_pdv(v),([f'{bad} visitas contradictorias excluidas.'] if bad else [])

def pdv_alerts(result,weights,kpi):
    if result.empty:return pd.DataFrame()
    a=result.copy();a['Peso KPI']=a['Canal'].map(weights['kpi'][kpi])
    a['Cumplimiento (%)']=a['Resultado']*100
    a['Prioridad pp']=(1-a['Resultado'])*a['Peso KPI']*100
    return a.sort_values('Prioridad pp',ascending=False)

def coverage(d):
    columns=['ID PDV']+DIMS+['PDV','Programadas','Realizadas','Atendido','Cubierto','Frecuencia']
    if d.empty:return pd.DataFrame(columns=columns)
    t=d.copy()
    t['Programadas']=number(t['Visitas Programadas']);t['Realizadas']=number(t['Visitas Realizadas'])
    t=t[t['Programadas'].ge(0)&t['Realizadas'].ge(0)]
    # Multiple assigned people: retain their programmed workload, then aggregate PDV.
    by=t.groupby(['ID PDV']+DIMS,dropna=False).agg(Programadas=('Programadas','sum'),Realizadas=('Realizadas','sum'),PDV=('PDV','first')).reset_index()
    by['Atendido']=by['Realizadas'].gt(0)
    by['Cubierto']=by['Programadas'].gt(0)&by['Atendido']
    by['Frecuencia']=by['Realizadas']/by['Programadas'].where(by['Programadas']>0)
    return by[columns]

def cover_stats(d):
    if d.empty:return {'Universo':0,'Atendidos':0,'Cobertura':np.nan,'Frecuencia':np.nan,'Programadas':0,'Realizadas':0}
    programmed=d[d['Programadas']>0]
    prog=programmed['Programadas'].sum();real=programmed['Realizadas'].sum()
    return {'Universo':len(programmed),'Atendidos':int(programmed['Cubierto'].sum()),
            'Cobertura':programmed['Cubierto'].mean() if len(programmed) else np.nan,
            'Frecuencia':real/prog if prog else np.nan,'Programadas':prog,'Realizadas':real}

def aggregate(result,dimensions):
    if result.empty:return pd.DataFrame(columns=dimensions+['Cumplimiento (%)','PDV'])
    return result.groupby(dimensions,dropna=False).agg(**{'Cumplimiento (%)':('Resultado',lambda x:x.mean()*100),'PDV':('ID PDV','nunique')}).reset_index()
