# Scenario Configs

Section `03` uses the canonical generator configuration at
[`configs/generator/base.yaml`](../generator/base.yaml). The `drift`
configuration owns the reproducible `customer_order_frequency` scenario:
pre-drift and post-drift windows, the fixed seven-day feature cutoff, the
successful-payment label horizon, and the warning/alert PSI thresholds.

The scenario is a local, offline contract for a campaign-period change in
customer order frequency. It is intentionally deterministic for a selected
scale and seed, while the implementation remains reusable for later category-
mix or traffic-pattern scenarios. This file documents ownership; the
canonical YAML values remain in `configs/generator/base.yaml`.
