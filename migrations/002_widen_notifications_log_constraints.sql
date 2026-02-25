-- Widen CHECK constraints on notifications_log to support webhook, gate, and
-- scheduler notification types introduced by the webhook receiver and
-- grace-period scheduler.

-- Channel: add 'webhook', 'system', 'api', 'mock', 'db_direct'
ALTER TABLE notifications_log DROP CONSTRAINT IF EXISTS notifications_log_channel_check;
ALTER TABLE notifications_log ADD CONSTRAINT notifications_log_channel_check
  CHECK (channel IN ('push', 'sms', 'webhook', 'system', 'api', 'mock', 'db_direct'));

-- Notification type: add 'gate_authorization', 'grace_period_expired', 'operator_session_update'
ALTER TABLE notifications_log DROP CONSTRAINT IF EXISTS notifications_log_notification_type_check;
ALTER TABLE notifications_log ADD CONSTRAINT notifications_log_notification_type_check
  CHECK (notification_type IN (
    'fee_increase_warning', 'payment_confirmed', 'grace_period_warning',
    'session_created', 'gate_authorization', 'grace_period_expired',
    'operator_session_update'
  ));
