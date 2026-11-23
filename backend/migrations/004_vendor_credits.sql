CREATE TABLE IF NOT EXISTS vendor_credit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    shipment_id bigint NOT NULL REFERENCES vendor_shipment(id),
    proposal_ref text NOT NULL UNIQUE,
    units integer NOT NULL CHECK (units > 0),
    unit_price_cents integer NOT NULL CHECK (unit_price_cents > 0),
    freight_cents bigint NOT NULL CHECK (freight_cents >= 0),
    net_cents bigint GENERATED ALWAYS AS (units::bigint * unit_price_cents - freight_cents) STORED,
    note text NOT NULL,
    submitted_by text NOT NULL REFERENCES staff(login),
    submitted_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','rejected')),
    reviewed_by text REFERENCES staff(login),
    acknowledged_ref text UNIQUE,
    review_note text,
    reviewed_at timestamptz,
    CHECK (freight_cents < units::bigint * unit_price_cents),
    CHECK ((status='pending') = (reviewed_by IS NULL AND reviewed_at IS NULL)),
    CHECK ((status='accepted') = (acknowledged_ref IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS vendor_credit_live_shipment ON vendor_credit(shipment_id) WHERE status <> 'rejected';
