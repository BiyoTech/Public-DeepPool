-- Migration 005: create payment_orders table for third-party payment (WeChat/Alipay) recharge orders.
-- IMPORTANT: Run this migration BEFORE deploying the new Go code if the database already exists.
-- For fresh deployments, the table is auto-created by SchemaDDL in server.go.

CREATE TABLE IF NOT EXISTS payment_orders (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    order_no       VARCHAR(32) NOT NULL COMMENT 'merchant order number, e.g. DP17127654321001234',
    user_id        BIGINT UNSIGNED NOT NULL,
    channel        VARCHAR(16) NOT NULL COMMENT 'payment channel: wechat / alipay',
    amount         DECIMAL(20,10) NOT NULL COMMENT 'recharge amount in yuan',
    status         VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending / paid / expired / closed',
    qr_url         TEXT NOT NULL COMMENT 'payment URL: QR code URL (wechat) or redirect URL (alipay page pay)',
    transaction_id VARCHAR(128) DEFAULT NULL COMMENT 'third-party platform transaction ID',
    paid_at        DATETIME DEFAULT NULL COMMENT 'payment confirmation time',
    expires_at     DATETIME NOT NULL COMMENT 'order expiry time',
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_payment_order_no (order_no),
    INDEX idx_payment_user (user_id),
    INDEX idx_payment_status_expires (status, expires_at),
    CONSTRAINT fk_payment_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
