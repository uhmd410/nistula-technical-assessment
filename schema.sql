-- ============================================================
-- NISTULA UNIFIED MESSAGING PLATFORM — PostgreSQL Schema
-- ============================================================
-- Design goals:
--   1. One guest record across all channels (guest_channels maps identifiers)
--   2. All messages in a single table regardless of source channel
--   3. Conversations link guests to reservations
--   4. Full AI audit trail: drafted, edited, auto-sent
--   5. AI confidence score and query type stored per inbound message
-- ============================================================

-- ---------- ENUM TYPES ----------

CREATE TYPE channel_type AS ENUM (
    'whatsapp',
    'booking_com',
    'airbnb',
    'instagram',
    'direct'
);

-- Query classification categories
CREATE TYPE query_type AS ENUM (
    'pre_sales_availability',
    'pre_sales_pricing',
    'post_sales_checkin',
    'special_request',
    'complaint',
    'general_enquiry'
);

-- Message direction
CREATE TYPE message_direction AS ENUM (
    'inbound',   -- from guest
    'outbound'   -- from Nistula (AI or agent)
);

-- How the outbound message was produced/handled
CREATE TYPE response_status AS ENUM (
    'ai_drafted',      -- AI generated, not yet reviewed
    'agent_edited',    -- AI generated then edited by a human agent
    'auto_sent',       -- AI generated and sent automatically (high confidence)
    'manual'           -- Written entirely by a human agent
);

-- Routing action determined by confidence score
CREATE TYPE action_type AS ENUM (
    'auto_send',
    'agent_review',
    'escalate'
);

-- Reservation status
CREATE TYPE reservation_status AS ENUM (
    'confirmed',
    'checked_in',
    'checked_out',
    'cancelled',
    'no_show'
);

-- Conversation status
CREATE TYPE conversation_status AS ENUM (
    'open',
    'resolved',
    'escalated'
);


-- ============================================================
-- 1. GUESTS
-- One canonical record per guest, regardless of how many channels
-- they contact us from. De-duplication happens at the application
-- layer (matching by email or phone).
-- ============================================================

CREATE TABLE guests (
    id              BIGSERIAL       PRIMARY KEY,
    full_name       VARCHAR(200)    NOT NULL,
    email           VARCHAR(255)    UNIQUE,                     -- nullable: not all channels provide email
    phone           VARCHAR(30)     UNIQUE,                     -- nullable: same reason
    notes           TEXT,                                        -- internal notes about the guest
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Index for fast lookups by email and phone (used in de-duplication)
CREATE INDEX idx_guests_email ON guests (email) WHERE email IS NOT NULL;
CREATE INDEX idx_guests_phone ON guests (phone) WHERE phone IS NOT NULL;

COMMENT ON TABLE guests IS 'Canonical guest profiles — one record per guest across all channels.';


-- ============================================================
-- 2. GUEST CHANNELS
-- Maps a guest to their identifier on each messaging channel.
-- A single guest can appear on multiple channels (e.g. WhatsApp
-- phone number AND Airbnb profile ID).
-- ============================================================

CREATE TABLE guest_channels (
    id                   BIGSERIAL       PRIMARY KEY,
    guest_id             BIGINT          NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
    channel              channel_type    NOT NULL,
    channel_identifier   VARCHAR(255)    NOT NULL,    -- e.g. phone number, Airbnb profile ID
    is_primary           BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- A channel + identifier pair must be unique (one WhatsApp number = one mapping)
    CONSTRAINT uq_channel_identifier UNIQUE (channel, channel_identifier)
);

CREATE INDEX idx_guest_channels_guest_id ON guest_channels (guest_id);

COMMENT ON TABLE guest_channels IS 'Maps guests to their per-channel identifiers for cross-channel identity resolution.';


-- ============================================================
-- 3. PROPERTIES
-- Reference table for managed properties.
-- ============================================================

CREATE TABLE properties (
    id              BIGSERIAL       PRIMARY KEY,
    property_code   VARCHAR(50)     NOT NULL UNIQUE,             -- e.g. "villa-b1"
    name            VARCHAR(200)    NOT NULL,
    location        VARCHAR(300),
    bedrooms        SMALLINT,
    max_guests      SMALLINT,
    base_rate       NUMERIC(10, 2),                              -- per night in INR
    metadata        JSONB           DEFAULT '{}'::JSONB,         -- flexible key-value store for extras
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE properties IS 'Managed properties/villas with their configuration and pricing.';


-- ============================================================
-- 4. RESERVATIONS
-- Booking records linking guests to properties with dates.
-- ============================================================

CREATE TABLE reservations (
    id              BIGSERIAL           PRIMARY KEY,
    booking_ref     VARCHAR(50)         NOT NULL UNIQUE,         -- e.g. "NIS-2024-0891"
    guest_id        BIGINT              NOT NULL REFERENCES guests(id) ON DELETE RESTRICT,
    property_id     BIGINT              NOT NULL REFERENCES properties(id) ON DELETE RESTRICT,
    check_in        DATE                NOT NULL,
    check_out       DATE                NOT NULL,
    num_guests      SMALLINT            NOT NULL DEFAULT 1,
    total_amount    NUMERIC(12, 2),                              -- in INR
    status          reservation_status  NOT NULL DEFAULT 'confirmed',
    notes           TEXT,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_dates CHECK (check_out > check_in)
);

CREATE INDEX idx_reservations_booking_ref ON reservations (booking_ref);
CREATE INDEX idx_reservations_guest_id    ON reservations (guest_id);
CREATE INDEX idx_reservations_property_id ON reservations (property_id);
CREATE INDEX idx_reservations_dates       ON reservations (check_in, check_out);

COMMENT ON TABLE reservations IS 'Booking records linking guests to properties with date ranges and status.';


-- ============================================================
-- 5. CONVERSATIONS
-- Groups messages into threaded conversations. A conversation
-- belongs to a guest and may optionally be linked to a reservation.
-- ============================================================

CREATE TABLE conversations (
    id              BIGSERIAL               PRIMARY KEY,
    guest_id        BIGINT                  NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
    reservation_id  BIGINT                  REFERENCES reservations(id) ON DELETE SET NULL,  -- nullable: pre-booking enquiries have no reservation
    channel         channel_type            NOT NULL,
    status          conversation_status     NOT NULL DEFAULT 'open',
    created_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_guest_id       ON conversations (guest_id);
CREATE INDEX idx_conversations_reservation_id ON conversations (reservation_id) WHERE reservation_id IS NOT NULL;
CREATE INDEX idx_conversations_status         ON conversations (status);

COMMENT ON TABLE conversations IS 'Threaded conversations grouping messages by guest and optional reservation.';


-- ============================================================
-- 6. MESSAGES
-- All messages across all channels in one table. Both inbound
-- (guest → Nistula) and outbound (Nistula → guest) messages
-- live here. AI-specific fields are nullable since they only
-- apply to inbound messages and their AI-drafted responses.
-- ============================================================

CREATE TABLE messages (
    id                  BIGSERIAL           PRIMARY KEY,
    message_id          UUID                NOT NULL UNIQUE DEFAULT gen_random_uuid(),   -- public-facing ID
    conversation_id     BIGINT              NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    direction           message_direction   NOT NULL,
    message_text        TEXT                NOT NULL,
    timestamp           TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    -- AI classification (inbound messages only)
    query_type          query_type,                                          -- NULL for outbound messages
    ai_confidence_score NUMERIC(4, 3)       CHECK (ai_confidence_score BETWEEN 0 AND 1),  -- e.g. 0.910

    -- AI response tracking (outbound messages only)
    response_status     response_status,                                     -- how the reply was produced
    drafted_reply       TEXT,                                                -- original AI-generated text (before edits)
    final_reply         TEXT,                                                -- what was actually sent to guest
    action_taken        action_type,                                         -- auto_send / agent_review / escalate

    -- Metadata
    source_channel      channel_type        NOT NULL,                        -- denormalised for fast filtering
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON messages (conversation_id);
CREATE INDEX idx_messages_timestamp       ON messages (timestamp);
CREATE INDEX idx_messages_query_type      ON messages (query_type) WHERE query_type IS NOT NULL;
CREATE INDEX idx_messages_action_taken    ON messages (action_taken) WHERE action_taken IS NOT NULL;
CREATE INDEX idx_messages_direction       ON messages (direction);

COMMENT ON TABLE messages IS 'Unified message store for all channels. Stores AI classification, confidence, and response audit trail.';


-- ============================================================
-- 7. MESSAGE AUDIT LOG
-- Tracks every edit made to an AI-drafted reply before it was
-- sent. Useful for training data, compliance, and agent
-- performance review.
-- ============================================================

CREATE TABLE message_audit_log (
    id              BIGSERIAL       PRIMARY KEY,
    message_id      BIGINT          NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    edited_by       VARCHAR(200)    NOT NULL,        -- agent name or "system"
    original_text   TEXT            NOT NULL,
    edited_text     TEXT            NOT NULL,
    edit_reason     VARCHAR(500),                    -- optional explanation
    edited_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_message_id ON message_audit_log (message_id);

COMMENT ON TABLE message_audit_log IS 'Audit trail tracking edits from AI draft to final sent message.';


-- ============================================================
-- DESIGN DECISION COMMENTARY
-- ============================================================
--
-- HARDEST DESIGN DECISION: Where to store AI metadata.
--
-- I considered three approaches:
--
-- (a) Separate ai_responses table with a FK to messages.
--     Pro: Clean separation of concerns.
--     Con: Requires a JOIN on every message fetch — most queries need
--          this data. Also complicates the write path.
--
-- (b) JSONB column on messages for all AI-related fields.
--     Pro: Flexible, schema-free.
--     Con: Can't index individual fields efficiently, no type safety,
--          harder to query aggregate stats (e.g. avg confidence by type).
--
-- (c) Nullable columns directly on the messages table (CHOSEN).
--     Pro: Single table read, indexable columns, type-safe with CHECK
--          constraints, and nullable fields clearly express "this only
--          applies to inbound" vs "this only applies to outbound".
--     Con: Some columns are NULL depending on direction, which adds
--          minor conceptual complexity.
--
-- I chose (c) because the messaging platform's most frequent query
-- pattern is "fetch a conversation with all messages and their AI
-- metadata" — a single-table scan is ideal here. The nullable columns
-- are well-documented with comments and the direction enum makes it
-- clear which fields apply to which message type.
--
-- Additionally, denormalising source_channel onto messages (even though
-- it exists on conversations) enables fast per-channel analytics
-- without joining to conversations.
-- ============================================================
