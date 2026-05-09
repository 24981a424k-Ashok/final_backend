from loguru import logger
from sqlalchemy.orm import Session
from src.database.models import User, VerifiedNews, TrackNotification
from src.utils.twilio_helper import twilio_helper

class SmsNotifier:
    @staticmethod
    async def broadcast_breaking_news(db: Session, news_item: VerifiedNews):
        """
        Send SMS alerts to ALL users with a phone number for major breaking news (Impact Score >= 9).
        """
        if not news_item or news_item.impact_score is None or news_item.impact_score < 9:
            return

        logger.info(f"🚨 MAJOR BREAKING NEWS DETECTED: {news_item.title} (Score: {news_item.impact_score})")
        
        # 1. Fetch all users with a phone number
        users = db.query(User).filter(User.phone != None).all()
        
        # 2. Define message
        article_url = f"https://ai-news.uniintel.com/article/{news_item.id}"
        message_body = f"🚨 BREAKING: {news_item.title}\n\nImpact Score: {news_item.impact_score}/10\nRead More: {article_url}\n- AI News Intelligence"

        # 3. Add default test number if not in users list
        test_number = "+916281422690"
        recipient_phones = [u.phone for u in users]
        if test_number not in recipient_phones:
            logger.info(f"Adding default test recipient: {test_number}")
            try:
                await twilio_helper.send_sms(test_number, message_body)
            except Exception as e:
                logger.error(f"Failed to send test SMS to {test_number}: {e}")

        count = 0
        for user in users:
            # CHECK HISTORY: Simple check to avoid double-sending the same breaking news item
            already_notified = db.query(TrackNotification).filter(
                TrackNotification.user_id == user.id,
                TrackNotification.news_id == news_item.id
            ).first()
            
            if already_notified:
                continue

            try:
                success = await twilio_helper.send_sms(user.phone, message_body)
                if success:
                    # Record that we notified them
                    db.add(TrackNotification(user_id=user.id, news_id=news_item.id))
                    count += 1
            except Exception as e:
                logger.error(f"Failed to send breaking SMS to {user.phone}: {e}")

        db.commit()
        logger.info(f"Broadcasted breaking news SMS to {count} users + testing number.")
