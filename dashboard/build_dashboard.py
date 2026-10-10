"""Build the interactive Olist dashboard (dashboard/index.html).

Joins the pipeline export (exports/fact_orders.csv) with the raw Olist tables in data/raw
to add delivery stages, seller handoff, distance, category, basket and review-comment
features, then embeds a compact column-encoded dataset in dashboard/template.html.

Run from the project root after the pipeline has produced exports/:
    python dashboard/build_dashboard.py
"""
import base64, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
STATES = [("AC","Acre","North"),("AL","Alagoas","Northeast"),("AP","Amapá","North"),("AM","Amazonas","North"),("BA","Bahia","Northeast"),
          ("CE","Ceará","Northeast"),("DF","Distrito Federal","Central-West"),("ES","Espírito Santo","Southeast"),("GO","Goiás","Central-West"),
          ("MA","Maranhão","Northeast"),("MT","Mato Grosso","Central-West"),("MS","Mato Grosso do Sul","Central-West"),("MG","Minas Gerais","Southeast"),
          ("PA","Pará","North"),("PB","Paraíba","Northeast"),("PR","Paraná","South"),("PE","Pernambuco","Northeast"),("PI","Piauí","Northeast"),
          ("RJ","Rio de Janeiro","Southeast"),("RN","Rio Grande do Norte","Northeast"),("RS","Rio Grande do Sul","South"),("RO","Rondônia","North"),
          ("RR","Roraima","North"),("SC","Santa Catarina","South"),("SP","São Paulo","Southeast"),("SE","Sergipe","Northeast"),("TO","Tocantins","North")]


def enrich():
    f = pd.read_csv(ROOT / 'exports' / 'fact_orders.csv', parse_dates=['purchased_at', 'delivered_at', 'estimated_at'])
    o = pd.read_csv(RAW / 'olist_orders_dataset.csv', parse_dates=['order_approved_at', 'order_delivered_carrier_date'])
    it = pd.read_csv(RAW / 'olist_order_items_dataset.csv', parse_dates=['shipping_limit_date'])
    pr = pd.read_csv(RAW / 'olist_products_dataset.csv')
    tr = pd.read_csv(RAW / 'product_category_name_translation.csv')
    se = pd.read_csv(RAW / 'olist_sellers_dataset.csv')
    cu = pd.read_csv(RAW / 'olist_customers_dataset.csv')
    rv = pd.read_csv(RAW / 'olist_order_reviews_dataset.csv', parse_dates=['review_creation_date', 'review_answer_timestamp'])
    ge = pd.read_csv(RAW / 'olist_geolocation_dataset.csv')
    f = f.merge(o[['order_id', 'customer_id', 'order_approved_at', 'order_delivered_carrier_date']], on='order_id', how='left')
    f = f.merge(cu[['customer_id', 'customer_unique_id', 'customer_zip_code_prefix']], on='customer_id', how='left')
    # same review rule as the pipeline: latest answered review per order
    r = rv.dropna(subset=['review_score']).sort_values(['order_id', 'review_answer_timestamp', 'review_creation_date', 'review_id']).groupby('order_id').tail(1)
    r['comment'] = r.review_comment_message.notna() & (r.review_comment_message.astype(str).str.strip() != '')
    f = f.merge(r[['order_id', 'review_score', 'comment']].rename(columns={'review_score': 'rs2'}), on='order_id', how='left')
    assert ((f.review_score.fillna(-1)) == (f.rs2.fillna(-1))).all(), 'review selection differs from the pipeline'
    it = it.merge(pr[['product_id', 'product_category_name']], on='product_id', how='left').merge(tr, on='product_category_name', how='left')
    it['cat'] = it.product_category_name_english.fillna(it.product_category_name).fillna('unknown')
    it = it.merge(se[['seller_id', 'seller_zip_code_prefix', 'seller_state']], on='seller_id', how='left')
    agg = it.groupby('order_id').agg(items=('order_item_id', 'size'), price=('price', 'sum'), ship_limit=('shipping_limit_date', 'max'))
    top = it.sort_values(['order_id', 'price'], ascending=[True, False]).groupby('order_id').head(1)[['order_id', 'cat', 'seller_zip_code_prefix', 'seller_state']]
    f = f.merge(agg, on='order_id', how='left').merge(top, on='order_id', how='left')
    # distance between zip-prefix centroids (highest-value item's seller)
    gc = ge.groupby('geolocation_zip_code_prefix')[['geolocation_lat', 'geolocation_lng']].median()
    def ll(z):
        x = gc.reindex(z)
        return x.geolocation_lat.values, x.geolocation_lng.values
    a1, o1 = ll(f.customer_zip_code_prefix); a2, o2 = ll(f.seller_zip_code_prefix)
    la1, lo1, la2, lo2 = map(np.radians, [a1, o1, a2, o2])
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    f['dist'] = 6371 * 2 * np.arcsin(np.sqrt(h))
    f.loc[f.dist > 4500, 'dist'] = np.nan  # geolocation outliers outside Brazil
    D = lambda a, b: (f[b] - f[a]).dt.total_seconds() / 86400
    f['appr'] = D('purchased_at', 'order_approved_at')
    f['handle'] = D('order_approved_at', 'order_delivered_carrier_date')
    f['transit'] = D('order_delivered_carrier_date', 'delivered_at')
    f['promise'] = (f.estimated_at.dt.normalize() - f.purchased_at.dt.normalize()).dt.days
    f['actual'] = D('purchased_at', 'delivered_at')
    f['late_handoff'] = f.order_delivered_carrier_date > f.ship_limit
    for c in ['appr', 'handle', 'transit']:
        f.loc[(f[c] < 0) | (f[c] > 200), c] = np.nan
    f = f.sort_values('purchased_at')
    f['first'] = f.groupby('customer_unique_id').cumcount() == 0
    f['came_back'] = f.groupby('customer_unique_id').order_id.transform('size') > 1
    return f.sort_values('order_id').reset_index(drop=True), it


def encode(f, it):
    ci = {s[0]: i for i, s in enumerate(STATES)}
    months = sorted(f.purchased_at.dt.strftime('%Y-%m').unique()); mi = {m: i for i, m in enumerate(months)}
    cats = f.cat.value_counts().index.tolist(); cati = {c: i for i, c in enumerate(cats)}
    e = lambda a, dt: base64.b64encode(np.ascontiguousarray(a, dtype=dt).tobytes()).decode()
    def u16(s, scale=1):
        x = np.round(np.asarray(s, float) * scale)
        return np.where(np.isnan(x), 65535, np.clip(x, 0, 65534))
    cols = {
        'mi': e(f.purchased_at.dt.strftime('%Y-%m').map(mi), '<u1'), 'cs': e(f.customer_state.map(ci), '<u1'),
        'ss': e(f.seller_state.map(ci).fillna(27), '<u1'), 'd': e(f.delay_days, '<i2'), 'sc': e(f.review_score.fillna(0), '<u1'),
        'cat': e(f.cat.map(cati), '<u1'), 'dist': e(u16(f.dist), '<u2'), 'prom': e(np.clip(f.promise, 0, 255), '<u1'),
        'act': e(u16(f.actual, 10), '<u2'), 'appr': e(u16(f.appr, 10), '<u2'), 'hand': e(u16(f.handle, 10), '<u2'),
        'tran': e(u16(f.transit, 10), '<u2'), 'lh': e(f.late_handoff.astype(int), '<u1'), 'cm': e(f.comment.fillna(False).astype(int), '<u1'),
        'items': e(np.clip(f['items'], 0, 255), '<u1'), 'price': e(u16(f.price), '<u2'), 'first': e(f['first'].astype(int), '<u1'),
        'back': e(f.came_back.astype(int), '<u1'),
    }
    oi = {o: i for i, o in enumerate(f.order_id)}
    br = it[it.order_id.isin(oi)][['order_id', 'seller_id', 'seller_state']].drop_duplicates(['order_id', 'seller_id'])
    sel = br.drop_duplicates('seller_id')[['seller_id', 'seller_state']].reset_index(drop=True)
    si = {s: i for i, s in enumerate(sel.seller_id)}
    cols['bo'] = e(br.order_id.map(oi), '<u4'); cols['bs'] = e(br.seller_id.map(si), '<u2')
    return {'n': len(f), 'months': months, 'states': STATES, 'cats': [c.replace('_', ' ') for c in cats],
            'sellers': sel.values.tolist(), 'cols': cols}


def main():
    f, it = enrich()
    data = encode(f, it)
    tpl = (Path(__file__).parent / 'template.html').read_text()
    (Path(__file__).parent / 'index.html').write_text(tpl.replace('__DATA__', json.dumps(data, separators=(',', ':'))))
    print(f"dashboard/index.html written for {data['n']:,} delivered orders")


if __name__ == '__main__':
    main()
