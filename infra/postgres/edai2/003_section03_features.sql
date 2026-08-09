CREATE TABLE edai2_section03_version (
    manifest_sha256 CHAR(64) PRIMARY KEY,
    label_sha256 CHAR(64) NOT NULL,
    training_sha256 CHAR(64) NOT NULL,
    health_sha256 CHAR(64) NOT NULL,
    feature_cutoff TIMESTAMPTZ NOT NULL,
    baseline_date DATE NOT NULL,
    training_count INTEGER NOT NULL CHECK (training_count > 0),
    health_count INTEGER NOT NULL CHECK (health_count > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE edai2_section03_training_row (
    manifest_sha256 CHAR(64) NOT NULL REFERENCES edai2_section03_version(manifest_sha256),
    id TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    label SMALLINT NOT NULL CHECK (label IN (0, 1)),
    f_customer_total_orders_90d BIGINT NOT NULL,
    f_customer_paid_revenue_90d DOUBLE PRECISION NOT NULL,
    f_customer_avg_order_value_90d DOUBLE PRECISION NOT NULL,
    f_customer_distinct_categories_90d BIGINT NOT NULL,
    f_stream_views_60m BIGINT NOT NULL,
    f_stream_add_to_cart_60m BIGINT NOT NULL,
    f_stream_checkout_started_60m BIGINT NOT NULL,
    f_stream_order_placed_60m BIGINT NOT NULL,
    f_stream_cart_to_purchase_ratio_60m DOUBLE PRECISION NOT NULL,
    created TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (manifest_sha256, id)
);

CREATE TABLE edai2_section03_health_row (
    manifest_sha256 CHAR(64) NOT NULL REFERENCES edai2_section03_version(manifest_sha256),
    monitoring_date DATE NOT NULL,
    feature_name TEXT NOT NULL CHECK (feature_name = 'f_customer_order_frequency_7d'),
    window_days SMALLINT NOT NULL CHECK (window_days = 7),
    baseline_date DATE NOT NULL,
    customer_count BIGINT NOT NULL CHECK (customer_count > 0),
    mean_value DOUBLE PRECISION NOT NULL,
    stddev_value DOUBLE PRECISION NOT NULL CHECK (stddev_value >= 0),
    psi_vs_baseline DOUBLE PRECISION NOT NULL CHECK (psi_vs_baseline >= 0),
    drift_status TEXT NOT NULL CHECK (drift_status IN ('stable', 'warning', 'alert')),
    warning_flag BOOLEAN NOT NULL,
    alert_flag BOOLEAN NOT NULL,
    CHECK ((psi_vs_baseline >= 0.15) = alert_flag),
    CHECK ((psi_vs_baseline >= 0.10) = warning_flag),
    CHECK (drift_status = CASE WHEN psi_vs_baseline >= 0.15 THEN 'alert' WHEN psi_vs_baseline >= 0.10 THEN 'warning' ELSE 'stable' END),
    PRIMARY KEY (manifest_sha256, monitoring_date, feature_name)
);

CREATE TABLE edai2_section03_active_version (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    manifest_sha256 CHAR(64) NULL REFERENCES edai2_section03_version(manifest_sha256),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO edai2_section03_active_version (singleton, manifest_sha256) VALUES (TRUE, NULL) ON CONFLICT (singleton) DO NOTHING;

CREATE VIEW edai2_section03_training_active AS
SELECT row.* FROM edai2_section03_active_version active
JOIN edai2_section03_training_row row ON row.manifest_sha256 = active.manifest_sha256
WHERE active.singleton;
CREATE VIEW edai2_section03_health_active AS
SELECT row.* FROM edai2_section03_active_version active
JOIN edai2_section03_health_row row ON row.manifest_sha256 = active.manifest_sha256
WHERE active.singleton;
CREATE INDEX edai2_section03_training_active_btree ON edai2_section03_training_row (manifest_sha256, id, event_timestamp);
CREATE INDEX edai2_section03_health_active_btree ON edai2_section03_health_row (manifest_sha256, feature_name, monitoring_date);

CREATE FUNCTION edai2_section03_prevent_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable Section 03 rows cannot be updated or deleted'; END; $$;
CREATE TRIGGER edai2_section03_version_immutable BEFORE UPDATE OR DELETE ON edai2_section03_version FOR EACH ROW EXECUTE FUNCTION edai2_section03_prevent_mutation();
CREATE TRIGGER edai2_section03_training_immutable BEFORE UPDATE OR DELETE ON edai2_section03_training_row FOR EACH ROW EXECUTE FUNCTION edai2_section03_prevent_mutation();
CREATE TRIGGER edai2_section03_health_immutable BEFORE UPDATE OR DELETE ON edai2_section03_health_row FOR EACH ROW EXECUTE FUNCTION edai2_section03_prevent_mutation();
