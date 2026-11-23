CREATE INDEX IF NOT EXISTS audit_improvement_submissions
    ON audit_event(subject, id DESC) WHERE action = 'improvement_submit';

CREATE TABLE IF NOT EXISTS stock_hold (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    improvement_id bigint NOT NULL UNIQUE REFERENCES improvement(id),
    batch_code text NOT NULL UNIQUE REFERENCES product_batch(code),
    hold_ref text NOT NULL UNIQUE,
    held_qty integer NOT NULL CHECK (held_qty > 0),
    note text NOT NULL,
    status text NOT NULL DEFAULT 'held' CHECK (status IN ('held', 'cleared')),
    recorded_by text NOT NULL REFERENCES staff(login),
    recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reinspection_round (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hold_id bigint NOT NULL REFERENCES stock_hold(id),
    submission_id bigint NOT NULL REFERENCES audit_event(id),
    supplier_proof_ref text NOT NULL,
    inspection_ref text NOT NULL UNIQUE,
    inventory_qty integer NOT NULL CHECK (inventory_qty > 0),
    sample_qty integer NOT NULL CHECK (sample_qty BETWEEN LEAST(12, inventory_qty) AND inventory_qty),
    defect_qty integer NOT NULL CHECK (defect_qty BETWEEN 0 AND sample_qty),
    outcome text GENERATED ALWAYS AS (CASE WHEN defect_qty = 0 THEN 'pass' ELSE 'fail' END) STORED,
    note text NOT NULL,
    recorded_by text NOT NULL REFERENCES staff(login),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (hold_id, submission_id),
    UNIQUE (id, hold_id)
);

CREATE TABLE IF NOT EXISTS stock_disposition (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hold_id bigint NOT NULL REFERENCES stock_hold(id),
    disposition_ref text NOT NULL UNIQUE,
    kind text NOT NULL CHECK (kind IN ('release', 'scrap', 'vendor_return')),
    quantity integer NOT NULL CHECK (quantity > 0),
    round_id bigint,
    note text NOT NULL,
    recorded_by text NOT NULL REFERENCES staff(login),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (round_id, hold_id) REFERENCES reinspection_round(id, hold_id),
    CHECK ((kind = 'release') = (round_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS stock_disposition_hold ON stock_disposition(hold_id, id);
