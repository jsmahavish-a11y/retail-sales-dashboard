# Retail Sales Dashboard (Streamlit + Plotly)

Interactive executive dashboard built on the cleaned retail transactions (`clean_dataset.csv`, Task 3).

## Features
- KPI cards: Revenue, Average Order Value, Transactions, Active customers, Customer Acquisition Cost, Churn rate (revenue/AOV/transactions show change vs the previous period of equal length)
- Slicers: date range, category, location, payment method, discount
- Revenue trend area chart with Year / Quarter / Month / Week / Day grain
- Revenue by category, payment mix, heatmaps (location x category, weekday x month)
- Drill-down: year > month > day, and category > item
- PDF export of the current view (sidebar: "Prepare PDF of this view")

## Assumptions and limits
- No marketing cost in the data: CAC uses an adjustable assumption (% of revenue).
- No geographic fields (location is Online / In-Store): heatmap compares channels instead of a map.
- Only 25 distinct customers: churn and CAC are illustrative.

## Run
pip install -r requirements.txt
streamlit run app.py
