"""Build powerbi/olist_powerbi_model.xlsx for Power BI (web): fact + seller table + state and date dimensions.

Run from the project root after the pipeline has produced exports/:
    python powerbi/build_powerbi_model.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STATES = [("AC","Acre","North"),("AL","Alagoas","Northeast"),("AP","Amapá","North"),("AM","Amazonas","North"),("BA","Bahia","Northeast"),
          ("CE","Ceará","Northeast"),("DF","Distrito Federal","Central-West"),("ES","Espírito Santo","Southeast"),("GO","Goiás","Central-West"),
          ("MA","Maranhão","Northeast"),("MT","Mato Grosso","Central-West"),("MS","Mato Grosso do Sul","Central-West"),("MG","Minas Gerais","Southeast"),
          ("PA","Pará","North"),("PB","Paraíba","Northeast"),("PR","Paraná","South"),("PE","Pernambuco","Northeast"),("PI","Piauí","Northeast"),
          ("RJ","Rio de Janeiro","Southeast"),("RN","Rio Grande do Norte","Northeast"),("RS","Rio Grande do Sul","South"),("RO","Rondônia","North"),
          ("RR","Roraima","North"),("SC","Santa Catarina","South"),("SP","São Paulo","Southeast"),("SE","Sergipe","Northeast"),("TO","Tocantins","North")]

fact = pd.read_csv(ROOT / 'exports' / 'fact_orders.csv', parse_dates=['purchased_at', 'delivered_at', 'estimated_at'])
fact['purchase_date'] = fact.purchased_at.dt.normalize()  # join key to dim_date
sellers = pd.read_csv(ROOT / 'exports' / 'seller_performance.csv')
dim_state = pd.DataFrame(STATES, columns=['state_code', 'state_name', 'region'])
dim_state['map_location'] = dim_state.state_name + ', Brazil'  # avoids "AL" mapping to Alabama
dim_date = pd.DataFrame({'date': pd.date_range('2016-01-01', '2018-12-31')})
dim_date['year'] = dim_date.date.dt.year
dim_date['quarter'] = 'Q' + dim_date.date.dt.quarter.astype(str)
dim_date['month_num'] = dim_date.date.dt.month
dim_date['month_name'] = dim_date.date.dt.strftime('%b')
dim_date['year_month'] = dim_date.date.dt.strftime('%Y-%m')
out = ROOT / 'powerbi' / 'olist_powerbi_model.xlsx'
with pd.ExcelWriter(out, engine='openpyxl') as w:
    fact.to_excel(w, sheet_name='fact_orders', index=False)
    sellers.to_excel(w, sheet_name='seller_performance', index=False)
    dim_state.to_excel(w, sheet_name='dim_state', index=False)
    dim_date.to_excel(w, sheet_name='dim_date', index=False)
print('written', out)
