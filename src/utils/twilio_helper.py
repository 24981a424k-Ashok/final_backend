import os
import asyncio
from twilio.rest import Client
from loguru import logger

class TwilioHelper:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_NUMBER")
        
        self.client = None
        if self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio Intelligence Node Initialized.")
            except Exception as e:
                logger.error(f"Twilio Init Failed: {e}")

    async def send_sms(self, to_number: str, message: str) -> bool:
        """
        Asynchronously send SMS using Twilio.
        Uses asyncio.to_thread to prevent blocking the event loop.
        """
        if not self.client:
            logger.warning(f"SMS Dispatch Skipped (Twilio offline). To: {to_number}")
            return False
        
        try:
            # Twilio's client.messages.create is a blocking network call
            loop = asyncio.get_event_loop()
            msg = await loop.run_in_executor(
                None, 
                lambda: self.client.messages.create(
                    body=message,
                    from_=self.from_number,
                    to=to_number
                )
            )
            logger.info(f"SMS Dispatch Successful: {msg.sid} to {to_number}")
            return True
        except Exception as e:
            logger.error(f"SMS Dispatch Failure to {to_number}: {e}")
            return False

    async def send_otp(self, to_number: str, otp: str) -> bool:
        """Sends a verification code via SMS."""
        message = f"Your UniIntel Verification Code: {otp}. Valid for 5 minutes."
        return await self.send_sms(to_number, message)

# Singleton instance
twilio_helper = TwilioHelper()
