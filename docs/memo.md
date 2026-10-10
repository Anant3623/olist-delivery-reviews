# Olist: delivery reliability and customer reviews

**Question and scope.** How do reviews differ when an order arrives after its estimated date, and where are delays concentrated? The analysis covers 96,470 delivered Brazilian Olist orders from 2016–2018 with valid purchase, promise, and delivery dates. A delivery is late when its *calendar date* is after the estimated date; 95,824 included orders have a review.

## Findings

1. **The gap persists within state and seller groups.** Late orders average **2.27/5** stars versus **4.29/5** on time, an unadjusted **2.02-point** difference. A two-sided Mann–Whitney U test gives **U = 103,305,546; p < 1e-300**. Scores are ordinal, so a rank test is preferable to a t-test for the formal comparison. Late-review-weighted gaps are **2.005 points across 21 qualifying customer states** and **1.971 across 287 qualifying participating sellers**. State and seller mix alone do not explain the gap, but these cuts are still observational.
2. **Ratings drop sharply after the promised date.** The exact-day mean is **4.33** at 10 days early, **4.03** on the promised date, **3.73** at one day late, and **1.91** at seven days late. A −20 to +20 day curve exposes the variation hidden inside a single “on-time” bucket.
3. **Rate and volume point to different priorities.** AL has the highest state late rate among states with at least 100 orders (**21.41%, 85/397**), followed by MA (**17.43%, 125/717**). RJ has **1,495** late orders; SP has **1,820** because of its much larger volume. March 2018's purchase cohort peaked at **18.96%** late across 7,003 orders. Distance from an SP state centroid correlates weakly with state late rate (**Spearman ρ = 0.278; p = 0.188**, 24 states); it does not establish a logistics cause.

## Actions

- Audit promised-date accuracy and carrier routes in AL and MA; investigate high-volume SP and RJ. Segment by seller origin, route, carrier, and product before assigning responsibility.
- Pilot alerts before the promised date and evaluate them in a controlled test. At the same order volume, cutting the late rate from **6.77% to 4.00%** means about **2,675 fewer late orders**. If those orders earned the observed on-time mean instead of the late mean and review participation stayed constant, the illustrative average review lift would be **~0.056 points**. This is a scenario, not a forecast.

**Limits.** Historical Brazil data may not describe today's operations. Product quality, price, carrier, and promise-setting can influence both delivery and review. The mart excludes **2,963 orders not marked delivered** and **8 delivered orders without delivery dates**, so selection bias is possible; missing reviews are omitted from score comparisons. Multi-seller orders appear in each participating seller's group. The observed association is not a causal estimate.
