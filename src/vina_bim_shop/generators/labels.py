from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

import numpy as np
import pandas as pd

from vina_bim_shop.generators.drift import DriftWindow


LABEL_COLUMNS: tuple[str, str] = ("id", "label")
FEATURE_COLUMNS: tuple[str, ...] = (
    "id",
    "event_timestamp",
    "f_customer_total_orders_90d",
    "f_customer_paid_revenue_90d",
    "f_customer_avg_order_value_90d",
    "f_customer_distinct_categories_90d",
    "f_stream_views_60m",
    "f_stream_add_to_cart_60m",
    "f_stream_checkout_started_60m",
    "f_stream_order_placed_60m",
    "f_stream_cart_to_purchase_ratio_60m",
    "created",
)
TRAINING_COLUMNS: tuple[str, ...] = (
    "id",
    "event_timestamp",
    "label",
    "f_customer_total_orders_90d",
    "f_customer_paid_revenue_90d",
    "f_customer_avg_order_value_90d",
    "f_customer_distinct_categories_90d",
    "f_stream_views_60m",
    "f_stream_add_to_cart_60m",
    "f_stream_checkout_started_60m",
    "f_stream_order_placed_60m",
    "f_stream_cart_to_purchase_ratio_60m",
    "created",
)
NORMALIZED_EVENT_COLUMNS: tuple[str, ...] = (
    "event_id",
    "event_type",
    "event_timestamp",
    "created_ts",
    "ingest_ts",
    "customer_id",
    "order_id",
    "product_id",
    "primary_category",
    "order_status",
    "order_net_amount",
)


def _utc(value: Any, *, name: str) -> pd.Timestamp:
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a valid timestamp") from exc
    if pd.isna(parsed):
        raise ValueError(f"{name} must be a valid timestamp")
    if parsed.tzinfo is None:
        return parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC")


def _utc_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        raise ValueError(f"{column} is required")
    parsed = pd.to_datetime(frame[column], errors="coerce", utc=True)
    if parsed.isna().any():
        raise ValueError(f"{column} must contain valid timestamps")
    return parsed


def _eligible_customers(customers: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    if "customer_id" not in customers:
        raise ValueError("customer_id is required")
    if customers["customer_id"].isna().any():
        raise ValueError("customer_id must not be null")
    if customers["customer_id"].astype("string").duplicated().any():
        raise ValueError("customer_id must be unique")
    output = customers[["customer_id"]].copy()
    output["created_ts"] = _utc_series(customers, "created_ts")
    output["customer_id"] = output["customer_id"].astype("string")
    return output.loc[output["created_ts"] <= cutoff].reset_index(drop=True)


def build_purchase_labels(
    customers: pd.DataFrame,
    payments: pd.DataFrame,
    *,
    window: DriftWindow,
) -> pd.DataFrame:
    cutoff = _utc(window.feature_cutoff_ts, name="feature_cutoff_ts")
    label_end = _utc(window.label_end_ts, name="label_end_ts")
    cohort = _eligible_customers(customers, cutoff)
    labels = cohort[["customer_id"]].rename(columns={"customer_id": "id"})
    labels["label"] = np.int8(0)
    if not payments.empty:
        for column in ("customer_id", "payment_status"):
            if column not in payments:
                raise ValueError(f"{column} is required")
        payment_times = _utc_series(payments, "payment_timestamp")
        created_times = _utc_series(payments, "created_ts")
        successful = (
            payments["payment_status"].astype("string").str.lower().eq("success")
            & payment_times.gt(cutoff)
            & payment_times.le(label_end)
            & created_times.le(label_end)
        )
        positive_ids = set(payments.loc[successful, "customer_id"].dropna().astype("string"))
        labels["label"] = labels["id"].isin(positive_ids).astype("int8")
    labels["id"] = labels["id"].astype("string")
    labels["label"] = labels["label"].astype("int8")
    return labels.sort_values("id", kind="stable").reset_index(drop=True)[list(LABEL_COLUMNS)]


def _mapping(value: Any, *, column: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{column} must contain a mapping or JSON object") from exc
        if isinstance(parsed, Mapping):
            return {str(key): item for key, item in parsed.items()}
    raise ValueError(f"{column} must contain a mapping or JSON object")


def normalize_commerce_events_for_features(
    topic_events: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    if "commerce_events" not in topic_events or topic_events["commerce_events"].empty:
        return pd.DataFrame(columns=list(NORMALIZED_EVENT_COLUMNS))
    raw = topic_events["commerce_events"].copy()
    required = ("event_id", "event_type", "event_timestamp", "created_ts", "correlation_ids", "payload")
    missing = [column for column in required if column not in raw]
    if missing:
        raise ValueError(f"commerce_events missing columns: {', '.join(missing)}")
    raw["event_timestamp"] = _utc_series(raw, "event_timestamp")
    raw["created_ts"] = _utc_series(raw, "created_ts")
    raw["ingest_ts"] = (
        _utc_series(raw, "ingest_ts") if "ingest_ts" in raw else raw["created_ts"].copy()
    )
    correlations = raw["correlation_ids"].map(lambda value: _mapping(value, column="correlation_ids"))
    payloads = raw["payload"].map(lambda value: _mapping(value, column="payload"))

    def coalesce(correlation: dict[str, Any], payload: dict[str, Any], key: str) -> Any:
        value = correlation.get(key)
        return value if value is not None else payload.get(key)

    normalized = pd.DataFrame(
        {
            "event_id": raw["event_id"].astype("string"),
            "event_type": raw["event_type"].astype("string"),
            "event_timestamp": raw["event_timestamp"],
            "created_ts": raw["created_ts"],
            "ingest_ts": raw["ingest_ts"],
            "customer_id": [
                coalesce(correlation, payload, "customer_id")
                for correlation, payload in zip(correlations, payloads, strict=True)
            ],
            "order_id": [
                coalesce(correlation, payload, "order_id")
                for correlation, payload in zip(correlations, payloads, strict=True)
            ],
            "product_id": [
                coalesce(correlation, payload, "product_id")
                for correlation, payload in zip(correlations, payloads, strict=True)
            ],
            "primary_category": [payload.get("primary_category") for payload in payloads],
            "order_status": [payload.get("order_status") for payload in payloads],
            "order_net_amount": [payload.get("order_net_amount") for payload in payloads],
        }
    )
    if normalized["event_id"].isna().any():
        raise ValueError("event_id must not be null")
    normalized = normalized.sort_values(
        ["event_id", "created_ts", "ingest_ts", "event_timestamp"],
        ascending=[True, False, False, False],
        kind="stable",
    ).reset_index(drop=True)
    winners: list[pd.Series] = []
    for event_id, group in normalized.groupby("event_id", sort=False, dropna=False):
        winner = group.iloc[0]
        tied = group.loc[
            group["created_ts"].eq(winner["created_ts"])
            & group["ingest_ts"].eq(winner["ingest_ts"])
            & group["event_timestamp"].eq(winner["event_timestamp"])
        ]
        if len(tied.drop_duplicates()) != 1:
            raise ValueError(f"ambiguous normalized winner for event_id {event_id}")
        winners.append(winner)
    output = pd.DataFrame(winners, columns=list(NORMALIZED_EVENT_COLUMNS))
    for column in ("customer_id", "order_id", "product_id", "primary_category", "order_status"):
        output[column] = output[column].astype("string")
    output["order_net_amount"] = pd.to_numeric(output["order_net_amount"], errors="coerce")
    return output.sort_values(["event_timestamp", "event_id"], kind="stable").reset_index(drop=True)


def build_point_in_time_customer_features(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    payments: pd.DataFrame,
    commerce_events: pd.DataFrame,
    *,
    window: DriftWindow,
) -> pd.DataFrame:
    cutoff = _utc(window.feature_cutoff_ts, name="feature_cutoff_ts")
    cohort = _eligible_customers(customers, cutoff)
    features = cohort[["customer_id"]].rename(columns={"customer_id": "id"})
    features["event_timestamp"] = cutoff
    customer_ids = set(features["id"])

    order_features = pd.DataFrame(columns=["id", "orders", "categories"])
    eligible_orders = orders.iloc[0:0].copy()
    if not orders.empty:
        for column in ("order_id", "customer_id", "primary_category"):
            if column not in orders:
                raise ValueError(f"{column} is required")
        order_times = _utc_series(orders, "order_timestamp")
        order_created = _utc_series(orders, "created_ts")
        lower = cutoff - pd.Timedelta(days=90)
        mask = (
            orders["customer_id"].astype("string").isin(customer_ids)
            & order_times.gt(lower)
            & order_times.le(cutoff)
            & order_created.le(cutoff)
        )
        eligible_orders = orders.loc[mask].copy()
        eligible_orders["customer_id"] = eligible_orders["customer_id"].astype("string")
        grouped = eligible_orders.groupby("customer_id", sort=False)
        order_features = pd.DataFrame(
            {
                "id": grouped.size().index.astype("string"),
                "orders": grouped.size().to_numpy(dtype=np.int64),
                "categories": grouped["primary_category"].nunique(dropna=True).to_numpy(dtype=np.int64),
            }
        )
    features = features.merge(order_features, on="id", how="left", validate="one_to_one")
    features["f_customer_total_orders_90d"] = features.pop("orders").fillna(0).astype("int64")
    features["f_customer_distinct_categories_90d"] = features.pop("categories").fillna(0).astype("int64")

    revenue = pd.DataFrame(columns=["id", "revenue", "paid_orders"])
    if not payments.empty:
        for column in ("order_id", "customer_id", "payment_status", "amount"):
            if column not in payments:
                raise ValueError(f"{column} is required")
        payment_times = _utc_series(payments, "payment_timestamp")
        payment_created = _utc_series(payments, "created_ts")
        mask = (
            payments["customer_id"].astype("string").isin(customer_ids)
            & payments["payment_status"].astype("string").str.lower().eq("success")
            & payments["order_id"].astype("string").isin(
                set(eligible_orders["order_id"].astype("string"))
            )
            & payment_times.gt(cutoff - pd.Timedelta(days=90))
            & payment_times.le(cutoff)
            & payment_created.le(cutoff)
        )
        paid = payments.loc[mask].copy()
        paid["customer_id"] = paid["customer_id"].astype("string")
        paid["amount"] = pd.to_numeric(paid["amount"], errors="raise")
        grouped = paid.groupby("customer_id", sort=False)
        revenue = pd.DataFrame(
            {
                "id": grouped.size().index.astype("string"),
                "revenue": grouped["amount"].sum().to_numpy(dtype=np.float64),
                "paid_orders": grouped["order_id"].nunique().to_numpy(dtype=np.int64),
            }
        )
    features = features.merge(revenue, on="id", how="left", validate="one_to_one")
    features["f_customer_paid_revenue_90d"] = features.pop("revenue").fillna(0.0).astype("float64")
    paid_orders = features.pop("paid_orders").fillna(0).astype("int64")
    features["f_customer_avg_order_value_90d"] = np.divide(
        features["f_customer_paid_revenue_90d"],
        paid_orders,
        out=np.zeros(len(features), dtype=np.float64),
        where=paid_orders.to_numpy() > 0,
    )

    stream_columns = {
        "product_viewed": "f_stream_views_60m",
        "add_to_cart": "f_stream_add_to_cart_60m",
        "checkout_started": "f_stream_checkout_started_60m",
        "order_placed": "f_stream_order_placed_60m",
    }
    for feature_name in stream_columns.values():
        features[feature_name] = np.int64(0)
    if not commerce_events.empty:
        event_times = _utc_series(commerce_events, "event_timestamp")
        event_created = _utc_series(commerce_events, "created_ts")
        stream_mask = (
            commerce_events["customer_id"].astype("string").isin(customer_ids)
            & event_times.gt(cutoff - pd.Timedelta(minutes=60))
            & event_times.le(cutoff)
            & event_created.le(cutoff)
        )
        selected = commerce_events.loc[stream_mask].copy()
        selected["customer_id"] = selected["customer_id"].astype("string")
        selected["event_hour"] = event_times.loc[selected.index].dt.floor("h")
        latest_hour = selected.groupby("customer_id")["event_hour"].transform("max")
        selected = selected.loc[selected["event_hour"].eq(latest_hour)]
        counts = selected.groupby(["customer_id", "event_type"]).size().unstack(fill_value=0)
        for event_type, feature_name in stream_columns.items():
            if event_type in counts:
                mapped = features["id"].map(counts[event_type]).fillna(0)
                features[feature_name] = mapped.astype("int64")
    features["f_stream_cart_to_purchase_ratio_60m"] = np.divide(
        features["f_stream_order_placed_60m"],
        features["f_stream_add_to_cart_60m"],
        out=np.zeros(len(features), dtype=np.float64),
        where=features["f_stream_add_to_cart_60m"].to_numpy() > 0,
    )
    features["created"] = cutoff
    features["id"] = features["id"].astype("string")
    return features.sort_values("id", kind="stable").reset_index(drop=True)[list(FEATURE_COLUMNS)]


def build_feature_label_join(
    labels: pd.DataFrame,
    features: pd.DataFrame,
) -> pd.DataFrame:
    if tuple(labels.columns) != LABEL_COLUMNS:
        raise ValueError("labels must have exact id,label schema")
    if labels["id"].isna().any() or labels["id"].duplicated().any():
        raise ValueError("labels.id must be non-null and unique")
    if not labels["label"].isin([0, 1]).all():
        raise ValueError("labels.label must be binary")
    if tuple(features.columns) != FEATURE_COLUMNS:
        raise ValueError("features have an unexpected schema")
    if features["id"].isna().any() or features["id"].duplicated().any():
        raise ValueError("features.id must be non-null and unique")
    joined = labels.merge(features, on="id", how="inner", validate="one_to_one")
    if len(joined) != len(labels):
        raise ValueError("every label must have exactly one feature row")
    return joined.sort_values("id", kind="stable").reset_index(drop=True)[list(TRAINING_COLUMNS)]


__all__ = [
    "FEATURE_COLUMNS",
    "LABEL_COLUMNS",
    "NORMALIZED_EVENT_COLUMNS",
    "TRAINING_COLUMNS",
    "build_feature_label_join",
    "build_point_in_time_customer_features",
    "build_purchase_labels",
    "normalize_commerce_events_for_features",
]
