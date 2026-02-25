import sys

from config import Config


class NotificationService:
    """SMS notification stub using Africa's Talking.

    When API credentials are configured the real SDK is used; otherwise
    messages are printed to stdout for local development.
    """

    def __init__(self):
        self.api_key = Config.AFRICASTALKING_API_KEY
        self.username = Config.AFRICASTALKING_USERNAME

    def send_sms(self, phone_number: str, message: str) -> bool:
        if self.api_key:
            try:
                import africastalking

                africastalking.initialize(self.username, self.api_key)
                sms = africastalking.SMS
                response = sms.send(message, [phone_number])
                print(f"SMS sent to {phone_number}: {response}")
                return True
            except Exception as e:
                print(f"SMS send failed: {e}", file=sys.stderr)
                return False
        else:
            # Dev mode — just print to console
            print(f"SMS to {phone_number}: {message}")
            return True

    def notify_payment_confirmed(self, session: dict) -> None:
        amount = session.get("amount_rwf", 0)
        grace = session.get("grace_period_minutes", 15)
        plate = session.get("plate_number", "")
        phone = session.get("phone_number", "")

        if not phone:
            return

        message = (
            f"SmartPark: Payment of {amount} RWF confirmed for {plate}. "
            f"You have {grace} minutes to exit. "
            f"The gate will open automatically."
        )
        self.send_sms(phone, message)

    def notify_fee_warning(self, session: dict, next_fee: int, payment_url: str) -> None:
        plate = session.get("plate_number", "")
        location = session.get("operator_location", "")
        phone = session.get("phone_number", "")

        if not phone:
            return

        message = (
            f"SmartPark: Your parking at {location} for {plate} "
            f"will increase to {next_fee} RWF soon. "
            f"Pay now: {payment_url}"
        )
        self.send_sms(phone, message)
