import sys
import time
import uuid

import psycopg2.extras
import requests

from config import Config

_token_cache = {"token": None, "expires_at": 0}


class MtnMomoClient:
    def __init__(self, db_conn):
        self.conn = db_conn
        self.base_url = Config.MTN_MOMO_BASE_URL
        self.subscription_key = Config.MTN_MOMO_SUBSCRIPTION_KEY
        self.api_user = Config.MTN_MOMO_API_USER
        self.api_key = Config.MTN_MOMO_API_KEY
        self.target_environment = Config.MTN_MOMO_TARGET_ENVIRONMENT
        self.currency = Config.MTN_MOMO_CURRENCY

    def get_access_token(self) -> str:
        if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
            return _token_cache["token"]

        resp = requests.post(
            f"{self.base_url}/collection/token/",
            auth=(self.api_user, self.api_key),
            headers={"Ocp-Apim-Subscription-Key": self.subscription_key},
        )
        resp.raise_for_status()
        data = resp.json()

        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)
        return _token_cache["token"]

    def request_to_pay(self, session_id: int, amount_rwf: int, phone_number: str, location_name: str) -> str:
        reference = str(uuid.uuid4())

        # Normalize phone: strip leading 0, prepend 250
        normalized = phone_number.lstrip("0")
        normalized = "250" + normalized

        token = self.get_access_token()

        body = {
            "amount": str(amount_rwf),
            "currency": self.currency,
            "externalId": str(session_id),
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": normalized,
            },
            "payerMessage": f"Parking fee at {location_name}",
            "payeeNote": f"SmartPark session {session_id}",
        }

        try:
            resp = requests.post(
                f"{self.base_url}/collection/v1_0/requesttopay",
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Reference-Id": reference,
                    "X-Target-Environment": self.target_environment,
                    "Ocp-Apim-Subscription-Key": self.subscription_key,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"MTN MoMo API error: {e}", file=sys.stderr)
            if hasattr(e, "response") and e.response is not None:
                print(f"Response body: {e.response.text}", file=sys.stderr)
            raise

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payments
                    (session_id, amount_rwf, payment_method, phone_number,
                     transaction_reference, status)
                VALUES (%s, %s, 'mtn_momo', %s, %s, 'pending')
                """,
                (session_id, amount_rwf, phone_number, reference),
            )
        self.conn.commit()

        return reference

    def check_payment_status(self, transaction_reference: str) -> str:
        token = self.get_access_token()

        resp = requests.get(
            f"{self.base_url}/collection/v1_0/requesttopay/{transaction_reference}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Target-Environment": self.target_environment,
                "Ocp-Apim-Subscription-Key": self.subscription_key,
            },
        )
        resp.raise_for_status()
        return resp.json()["status"]

    def confirm_payment(self, transaction_reference: str) -> dict:
        status = self.check_payment_status(transaction_reference)
        grace_minutes = Config.GRACE_PERIOD_MINUTES

        if status == "SUCCESSFUL":
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    UPDATE payments
                    SET status = 'completed',
                        confirmed_at = NOW(),
                        momo_transaction_id = %s
                    WHERE transaction_reference = %s
                    RETURNING session_id
                    """,
                    (transaction_reference, transaction_reference),
                )
                row = cur.fetchone()

                cur.execute(
                    f"""
                    UPDATE parking_sessions
                    SET status = 'paid',
                        grace_period_end = NOW() + INTERVAL '{int(grace_minutes)} minutes'
                    WHERE id = %s
                    RETURNING grace_period_end
                    """,
                    (row["session_id"],),
                )
                session_row = cur.fetchone()

            self.conn.commit()
            return {
                "success": True,
                "grace_period_end": session_row["grace_period_end"].isoformat(),
            }

        if status == "FAILED":
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE payments SET status = 'failed' WHERE transaction_reference = %s",
                    (transaction_reference,),
                )
            self.conn.commit()
            return {"success": False, "reason": "Payment was declined or cancelled"}

        # PENDING
        return {"success": None, "reason": "Payment still pending"}

    def get_pending_payment(self, session_id: int) -> dict | None:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM payments
                WHERE session_id = %s
                  AND status = 'pending'
                  AND initiated_at > NOW() - INTERVAL '5 minutes'
                ORDER BY initiated_at DESC
                LIMIT 1
                """,
                (session_id,),
            )
            return cur.fetchone()
