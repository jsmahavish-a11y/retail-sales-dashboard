# Data Quality Contract: Retail Orders

**Dataset:** `retail-orders-raw.csv` (9 columns, one row per order line)
**Decision owner:** Head of Sales & Operations (ed-tech business)
**Data owner (assumed role):** Order Systems / Data Engineering Lead
**Rules source:** `retail-data-dictionary.csv`
**Contract version:** 1.0

## Purpose

This contract states what "trustworthy" means for the retail orders data. If the data fails the thresholds below, KPIs built from it must not be published until the issue is fixed or formally accepted by the decision owner.

## Checks, thresholds and actions

Failure rate = failing rows / total rows. **Warn** means investigate within the SLA. **Fail** means block KPI publishing and escalate.

| # | Dimension | Check | Rule (from data dictionary) | Warn | Fail | Action on failure | Escalate to | Response time |
|---|---|---|---|---|---|---|---|---|
| 1 | Completeness | `order_date` present | Required | > 0% | > 2% | Quarantine rows, trace source system | Data owner | 1 working day |
| 2 | Completeness | `city` present and non-empty | Required, non-empty text | > 0% | > 2% | Quarantine rows, request fix from source | Data owner | 2 working days |
| 3 | Completeness | `discount_pct` present | Missing means zero only after justification | > 0% | > 5% | Do not assume zero; get written justification from Pricing | Pricing & Promotions Manager | 2 working days |
| 4 | Uniqueness | `order_id` unique | Required and unique | > 0% | > 0% | Remove extra copies, find the source of duplication, pause refresh if repeated | Data owner | Same working day |
| 5 | Validity | `order_date` is ISO `YYYY-MM-DD`, a real date, between 2025-01-01 and today | ISO date in range | > 0% | > 2% | Quarantine rows, fix format at source | Data owner | 1 working day |
| 6 | Validity | `quantity` is a whole number greater than zero | Whole number > 0 | > 0% | > 2% | Quarantine rows, check entry form validation | Data owner | 1 working day |
| 7 | Validity | `discount_pct` between 0 and 100 | 0 to 100 | > 0% | > 0% | Quarantine rows, review pricing rules | Pricing & Promotions Manager | 1 working day |
| 8 | Validity | `unit_price` is a non-negative INR amount | Non-negative | > 0% | > 0% | Quarantine rows, review price list | Pricing & Promotions Manager | 1 working day |
| 9 | Consistency | `customer_segment`, `category`, `payment_status` use the allowed values and one text format | Allowed values after normalization | > 0% | > 5% | Normalize casing in the pipeline, fix at source | Data owner | 3 working days |
| 10 | Freshness | Latest valid `order_date` is recent | Data should reflect current trading | Older than 2 days | Older than 7 days | Pause dashboard refresh, check the data feed | Data owner, then Head of Sales & Operations | Same working day |

## Escalation path

1. **Warn:** the analyst logs the issue and tells the data owner within the response time.
2. **Fail:** KPI publishing is paused. The data owner is told straight away, and the Head of Sales & Operations is told if not fixed within the response time.
3. **Repeated fail (3 refreshes in a row):** the issue becomes a standing agenda item for the decision owner and data owner until the root cause is fixed.

## Current result on the supplied file

Measured by the notebook `retail_data_quality_profile.ipynb` on 12 rows (11 unique orders).

| Check | Failing rows | Failure rate | Status |
|---|---|---|---|
| Missing `order_date` | 1 | 8.3% | Fail |
| Missing `city` | 1 | 8.3% | Fail |
| Missing `discount_pct` | 1 | 8.3% | Fail |
| Duplicate `order_id` (extra copies) | 1 | 8.3% | Fail |
| Invalid `order_date` (wrong format, impossible date, or missing) | 3 | 25.0% | Fail |
| Invalid `quantity` | 2 | 16.7% | Fail |
| `discount_pct` outside 0 to 100 | 1 | 8.3% | Fail |
| Inconsistent text case | 2 | 16.7% | Fail |
| Freshness (latest valid order 2026-01-18) | all rows | n/a | Fail |

**Overall: FAIL.** KPIs from this file must not be published as they stand. The notebook produces KPIs only from rows that pass every rule, and lists rejected rows for the data owner to correct.

## Assumptions

- Thresholds are proposed for this exercise and should be confirmed by the business.
- Owner names are role names, not real people.
- A row is "valid" only if it passes every rule above.
