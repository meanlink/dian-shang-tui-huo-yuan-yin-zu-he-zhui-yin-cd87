CREATE TABLE IF NOT EXISTS staff (
    login text PRIMARY KEY,
    password_hash text NOT NULL,
    display_name text NOT NULL,
    role text NOT NULL CHECK (role IN ('service', 'quality', 'supplier')),
    supplier text,
    CHECK ((role = 'supplier') = (supplier IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS product_batch (
    code text PRIMARY KEY,
    sku text NOT NULL,
    product text NOT NULL,
    supplier text NOT NULL,
    received_on date NOT NULL,
    delivered_qty integer NOT NULL CHECK (delivered_qty > 0),
    UNIQUE (code, sku)
);
CREATE TABLE IF NOT EXISTS reason_tag (
    code text PRIMARY KEY,
    name text UNIQUE NOT NULL,
    kind text NOT NULL CHECK (kind IN ('symptom', 'finding')),
    mutex text,
    CHECK ((kind = 'finding') = (mutex IS NULL))
);
CREATE TABLE IF NOT EXISTS return_case (
    ticket text PRIMARY KEY,
    order_ref text NOT NULL,
    sku text NOT NULL,
    batch_code text,
    opened_on date NOT NULL,
    detail text NOT NULL,
    finding text REFERENCES reason_tag(code),
    inspection_ref text,
    revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
    FOREIGN KEY (batch_code, sku) REFERENCES product_batch(code, sku),
    CHECK ((finding IS NULL) = (inspection_ref IS NULL))
);
CREATE INDEX IF NOT EXISTS return_case_scope ON return_case(sku, batch_code, opened_on);
CREATE TABLE IF NOT EXISTS return_symptom (
    ticket text REFERENCES return_case(ticket) ON DELETE CASCADE,
    tag text REFERENCES reason_tag(code),
    PRIMARY KEY(ticket, tag)
);
CREATE TABLE IF NOT EXISTS trace_run (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_code text NOT NULL REFERENCES product_batch(code),
    from_date date NOT NULL,
    through_date date NOT NULL CHECK (through_date >= from_date),
    requested_by text NOT NULL REFERENCES staff(login),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'ready', 'blocked', 'failed')),
    fingerprint text,
    coverage jsonb,
    message text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trace_run_queue ON trace_run(id) WHERE status = 'queued';
CREATE TABLE IF NOT EXISTS trace_rule (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES trace_run(id),
    symptoms text[] NOT NULL CHECK (cardinality(symptoms) BETWEEN 1 AND 2),
    finding text NOT NULL REFERENCES reason_tag(code),
    matched_count integer NOT NULL CHECK (matched_count >= 3),
    symptom_count integer NOT NULL,
    finding_count integer NOT NULL,
    eligible_count integer NOT NULL,
    evidence text[] NOT NULL CHECK (cardinality(evidence) = matched_count),
    decision text NOT NULL DEFAULT 'pending' CHECK (decision IN ('pending', 'confirmed', 'dismissed')),
    reviewer text REFERENCES staff(login),
    review_note text,
    UNIQUE (run_id, symptoms, finding),
    CHECK (eligible_count >= greatest(symptom_count, finding_count)),
    CHECK (matched_count <= least(symptom_count, finding_count))
);
CREATE TABLE IF NOT EXISTS improvement (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_id bigint UNIQUE NOT NULL REFERENCES trace_rule(id),
    batch_code text NOT NULL REFERENCES product_batch(code),
    finding text NOT NULL REFERENCES reason_tag(code),
    directive text NOT NULL,
    due_on date NOT NULL,
    status text NOT NULL DEFAULT 'assigned' CHECK (status IN ('assigned', 'working', 'verification', 'closed')),
    corrective_action text,
    proof_ref text,
    verification_note text,
    revised_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (batch_code, finding)
);
CREATE TABLE IF NOT EXISTS audit_event (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor text NOT NULL,
    action text NOT NULL,
    subject text NOT NULL,
    detail jsonb NOT NULL,
    happened_at timestamptz NOT NULL DEFAULT now()
);
