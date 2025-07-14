#!/usr/bin/env python3
"""
LuxuryTrendBot - Zero Friction Referral System
Automated Telegram Bot for Premium Money Opportunities
"""

import os
import sys
import asyncio
import logging
import random
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
BOT_USERNAME = os.getenv('BOT_USERNAME', '@LuxuryTrendBot')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('luxurytrend.log')
    ]
)
log = logging.getLogger(__name__)

@dataclass
class Offer:
    """Data class for offers"""
    id: Optional[int] = None
    title: str = ""
    description: str = ""
    category: str = ""
    commission: float = 0.0
    gravity: Optional[float] = None
    affiliate_link: str = ""
    platform: str = ""
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

@dataclass
class User:
    """Data class for users"""
    id: Optional[int] = None
    telegram_id: int = 0
    username: str = ""
    first_name: str = ""
    referral_code: str = ""
    referred_by: Optional[int] = None
    referral_count: int = 0
    points: int = 0
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

class Database:
    """Database manager for LuxuryTrendBot"""
    
    def __init__(self, db_path: str = "luxurytrend.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Offers table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS offers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        category TEXT,
                        commission REAL,
                        gravity REAL,
                        affiliate_link TEXT,
                        platform TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Users table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER UNIQUE NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        referral_code TEXT UNIQUE,
                        referred_by INTEGER,
                        referral_count INTEGER DEFAULT 0,
                        points INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (referred_by) REFERENCES users (telegram_id)
                    )
                ''')
                
                # Posts log table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS posts_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        offer_id INTEGER,
                        channel_id TEXT,
                        message_id INTEGER,
                        posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (offer_id) REFERENCES offers (id)
                    )
                ''')
                
                conn.commit()
                log.info("✅ Database initialized successfully")
                
        except Exception as e:
            log.error(f"❌ Database initialization failed: {e}")
            raise
    
    def add_offer(self, offer: Offer) -> int:
        """Add new offer to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO offers (title, description, category, commission, gravity, affiliate_link, platform)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (offer.title, offer.description, offer.category, offer.commission, 
                     offer.gravity, offer.affiliate_link, offer.platform))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            log.error(f"❌ Failed to add offer: {e}")
            return 0
    
    def get_random_offers(self, limit: int = 5) -> List[Offer]:
        """Get random offers from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM offers ORDER BY RANDOM() LIMIT ?', (limit,))
                rows = cursor.fetchall()
                
                offers = []
                for row in rows:
                    offer = Offer(
                        id=row[0], title=row[1], description=row[2], category=row[3],
                        commission=row[4], gravity=row[5], affiliate_link=row[6], platform=row[7]
                    )
                    offers.append(offer)
                return offers
        except Exception as e:
            log.error(f"❌ Failed to get offers: {e}")
            return []
    
    def add_user(self, user: User) -> bool:
        """Add new user to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users 
                    (telegram_id, username, first_name, referral_code, referred_by, referral_count, points)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user.telegram_id, user.username, user.first_name, user.referral_code,
                     user.referred_by, user.referral_count, user.points))
                conn.commit()
                return True
        except Exception as e:
            log.error(f"❌ Failed to add user: {e}")
            return False
    
    def get_user(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
                row = cursor.fetchone()
                
                if row:
                    return User(
                        id=row[0], telegram_id=row[1], username=row[2], first_name=row[3],
                        referral_code=row[4], referred_by=row[5], referral_count=row[6], points=row[7]
                    )
                return None
        except Exception as e:
            log.error(f"❌ Failed to get user: {e}")
            return None
    
    def update_referral_count(self, telegram_id: int) -> bool:
        """Update referral count for user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET referral_count = referral_count + 1, points = points + 100
                    WHERE telegram_id = ?
                ''', (telegram_id,))
                conn.commit()
                return True
        except Exception as e:
            log.error(f"❌ Failed to update referral count: {e}")
            return False
    
    def get_leaderboard(self, limit: int = 10) -> List[User]:
        """Get top referrers leaderboard"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM users ORDER BY referral_count DESC, points DESC LIMIT ?
                ''', (limit,))
                rows = cursor.fetchall()
                
                users = []
                for row in rows:
                    user = User(
                        id=row[0], telegram_id=row[1], username=row[2], first_name=row[3],
                        referral_code=row[4], referred_by=row[5], referral_count=row[6], points=row[7]
                    )
                    users.append(user)
                return users
        except Exception as e:
            log.error(f"❌ Failed to get leaderboard: {e}")
            return []

class OfferGenerator:
    """Generate realistic money-making offers"""
    
    def __init__(self):
        self.categories = ["AI Tools", "Crypto", "Business", "Marketing", "Health", "Finance"]
        self.platforms = ["ClickBank", "Digistore24", "JVZoo", "WarriorPlus"]
    
    def generate_offers(self, count: int = 30) -> List[Offer]:
        """Generate realistic offers"""
        offers = []
        
        offer_templates = [
            {
                "title": "AI Business Automation Suite",
                "description": "Complete AI-powered business automation platform with ChatGPT integration",
                "category": "AI Tools",
                "commission_range": (50, 200),
                "platform": "Digistore24"
            },
            {
                "title": "Crypto Trading Masterclass",
                "description": "Professional cryptocurrency trading course with live signals",
                "category": "Crypto",
                "commission_range": (75, 300),
                "platform": "ClickBank"
            },
            {
                "title": "Passive Income Blueprint",
                "description": "Step-by-step system to build multiple passive income streams",
                "category": "Business",
                "commission_range": (40, 150),
                "platform": "JVZoo"
            },
            {
                "title": "Social Media Marketing Agency Kit",
                "description": "Complete toolkit to start and scale a social media marketing agency",
                "category": "Marketing",
                "commission_range": (60, 250),
                "platform": "WarriorPlus"
            },
            {
                "title": "Keto Diet Transformation System",
                "description": "Comprehensive keto diet program with meal plans and coaching",
                "category": "Health",
                "commission_range": (30, 120),
                "platform": "ClickBank"
            },
            {
                "title": "Real Estate Investment Course",
                "description": "Learn to invest in real estate with no money down strategies",
                "category": "Finance",
                "commission_range": (80, 400),
                "platform": "Digistore24"
            }
        ]
        
        for i in range(count):
            template = random.choice(offer_templates)
            commission = random.uniform(*template["commission_range"])
            gravity = random.uniform(20, 100)
            
            offer = Offer(
                title=template["title"],
                description=template["description"],
                category=template["category"],
                commission=round(commission, 2),
                gravity=round(gravity, 1),
                affiliate_link=f"https://example.com/aff/{random.randint(1000, 9999)}",
                platform=template["platform"]
            )
            offers.append(offer)
        
        return offers

class ContentGenerator:
    """Generate engaging content for offers"""
    
    def __init__(self):
        self.emojis = {
            "AI Tools": "🤖",
            "Crypto": "₿",
            "Business": "💼",
            "Marketing": "📈",
            "Health": "💪",
            "Finance": "💰"
        }
    
    def generate_post(self, offer: Offer) -> str:
        """Generate engaging post content"""
        emoji = self.emojis.get(offer.category, "💎")
        
        urgency_phrases = [
            "⚡ LIMITED TIME ALERT!",
            "🔥 HOT OPPORTUNITY!",
            "⭐ TRENDING NOW!",
            "🚀 EXCLUSIVE ACCESS!",
            "💎 PREMIUM OPPORTUNITY!"
        ]
        
        cta_phrases = [
            "👆 Tap to claim your spot!",
            "🔗 Get instant access now!",
            "⚡ Start earning today!",
            "💰 Join thousands earning!",
            "🎯 Don't miss this chance!"
        ]
        
        urgency = random.choice(urgency_phrases)
        cta = random.choice(cta_phrases)
        
        post = f"""{urgency}

{emoji} **{offer.title}**

📋 {offer.description}

💵 **Commission:** ${offer.commission:.2f}
⭐ **Platform:** {offer.platform}
📈 **Category:** {offer.category}
🔥 **Popularity:** {offer.gravity}/100

{cta}

💎 Join @limitlesstrend_daily for daily opportunities!
🤖 Get your referral link: {BOT_USERNAME}"""

        return post

class LuxuryTrendBot:
    """Main bot class with zero friction referral system"""
    
    def __init__(self):
        self.db = Database()
        self.offer_generator = OfferGenerator()
        self.content_generator = ContentGenerator()
        self.app = None
        
        # Validate environment variables
        if not TELEGRAM_BOT_TOKEN:
            log.error("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
            sys.exit(1)
        
        if not TELEGRAM_CHANNEL_ID:
            log.error("❌ TELEGRAM_CHANNEL_ID not found in environment variables")
            sys.exit(1)
    
    def generate_referral_code(self) -> str:
        """Generate unique referral code"""
        import string
        chars = string.ascii_uppercase + string.digits
        return "LUX" + ''.join(random.choices(chars, k=6))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with referral processing"""
        user = update.effective_user
        args = context.args
        
        # Check if user came from referral link
        referrer_code = None
        if args and len(args) > 0:
            referrer_code = args[0]
        
        # Get or create user
        existing_user = self.db.get_user(user.id)
        
        if not existing_user:
            # Create new user
            new_user = User(
                telegram_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "",
                referral_code=self.generate_referral_code()
            )
            
            # Process referral if applicable
            if referrer_code and referrer_code.startswith("LUX"):
                # Find referrer
                with sqlite3.connect(self.db.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT telegram_id FROM users WHERE referral_code = ?', (referrer_code,))
                    referrer = cursor.fetchone()
                    
                    if referrer:
                        new_user.referred_by = referrer[0]
                        # Update referrer's count
                        self.db.update_referral_count(referrer[0])
                        
                        # Notify referrer
                        try:
                            await context.bot.send_message(
                                chat_id=referrer[0],
                                text=f"🎉 **New Referral!**\n\n"
                                     f"👤 {user.first_name} joined using your link!\n"
                                     f"💎 +100 points earned\n"
                                     f"🏆 Check your stats: /referral"
                            )
                        except:
                            pass  # Referrer might have blocked bot
            
            self.db.add_user(new_user)
            existing_user = new_user
        
        # Welcome message
        keyboard = [
            [InlineKeyboardButton("🎯 Get My Referral Link", callback_data="get_referral")],
            [InlineKeyboardButton("🏆 View Leaderboard", callback_data="leaderboard")],
            [InlineKeyboardButton("📊 Channel Stats", callback_data="stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""🎉 **Welcome to LuxuryTrendBot!**

Hi {user.first_name}! 👋

💎 **Your Benefits:**
✅ Premium money opportunities every 4 hours
✅ $150+ commission opportunities
✅ Zero friction referral system
✅ 100 points per successful referral

🎯 **Your Referral Code:** `{existing_user.referral_code}`
📊 **Your Stats:** {existing_user.referral_count} referrals, {existing_user.points} points

🚀 **Get Started:**
• Join @limitlesstrend_daily for opportunities
• Share your referral link to earn points
• Climb the leaderboard for rewards!

💰 **Start earning today!**"""

        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /referral command"""
        user = update.effective_user
        db_user = self.db.get_user(user.id)
        
        if not db_user:
            await update.message.reply_text("❌ Please start the bot first with /start")
            return
        
        referral_link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start={db_user.referral_code}"
        
        keyboard = [
            [InlineKeyboardButton("📱 Share on Telegram", url=f"https://t.me/share/url?url={referral_link}&text=💎 Join LuxuryTrendBot for premium money opportunities! Earn $150+ commissions automatically. 🚀")],
            [InlineKeyboardButton("🏆 View Leaderboard", callback_data="leaderboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        referral_text = f"""💎 **Your Referral Dashboard**

🎯 **Your Referral Link:**
`{referral_link}`

📊 **Your Performance:**
👥 **Referrals:** {db_user.referral_count}
💎 **Points:** {db_user.points}
🏆 **Rank:** Coming soon!

🚀 **How to Earn:**
1. Share your referral link
2. Get 100 points per new user
3. Climb the leaderboard
4. Unlock premium rewards

💰 **Share now and start earning!**"""

        await update.message.reply_text(referral_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /leaderboard command"""
        top_users = self.db.get_leaderboard(10)
        
        if not top_users:
            await update.message.reply_text("🏆 Leaderboard is empty. Be the first to refer someone!")
            return
        
        leaderboard_text = "🏆 **LuxuryTrendBot Leaderboard**\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        for i, user in enumerate(top_users):
            medal = medals[i] if i < 3 else f"{i+1}."
            name = user.first_name or user.username or "Anonymous"
            leaderboard_text += f"{medal} **{name}** - {user.referral_count} referrals ({user.points} points)\n"
        
        leaderboard_text += "\n💎 Share your referral link to climb the ranks!"
        
        keyboard = [[InlineKeyboardButton("🎯 Get My Referral Link", callback_data="get_referral")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(leaderboard_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """🤖 **LuxuryTrendBot Commands**

🎯 **Main Commands:**
/start - Welcome & setup your account
/referral - Get your referral link & stats
/leaderboard - View top referrers
/help - Show this help message

💎 **How It Works:**
1. Join @limitlesstrend_daily for opportunities
2. Share your referral link to earn points
3. Get 100 points per successful referral
4. Climb leaderboard for rewards

🚀 **Features:**
✅ Premium opportunities every 4 hours
✅ $150+ commission opportunities  
✅ Zero friction referral system
✅ Viral growth mechanics

💰 **Start earning today!**"""

        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "get_referral":
            await self.referral_command(update, context)
        elif query.data == "leaderboard":
            await self.leaderboard_command(update, context)
        elif query.data == "stats":
            stats_text = f"""📊 **LuxuryTrendBot Stats**

🤖 **Bot Status:** ✅ Online
📺 **Channel:** @limitlesstrend_daily
⏰ **Posting:** Every 4 hours
💎 **Opportunities:** Premium quality

🚀 **Join the community and start earning!**"""
            await query.edit_message_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def post_to_channel(self):
        """Post opportunity to channel"""
        try:
            offers = self.db.get_random_offers(1)
            if not offers:
                log.warning("⚠️ No offers available for posting")
                return
            
            offer = offers[0]
            content = self.content_generator.generate_post(offer)
            
            # Send to channel
            await self.app.bot.send_message(
                chat_id=TELEGRAM_CHANNEL_ID,
                text=content,
                parse_mode=ParseMode.MARKDOWN
            )
            
            log.info(f"✅ Posted offer to channel: {offer.title}")
            
        except Exception as e:
            log.error(f"❌ Failed to post to channel: {e}")
    
    async def scheduled_posts(self, context: ContextTypes.DEFAULT_TYPE):
        """Scheduled posting job"""
        await self.post_to_channel()
    
    def start_bot(self):
        """Start the bot"""
        try:
            log.info("🚀 Starting LuxuryTrendBot (Simplified)...")
            log.info("=" * 50)
            log.info("🤖 LuxuryTrendBot | Zero Friction Referrals")
            log.info("=" * 50)
            
            # Generate initial offers if database is empty
            existing_offers = self.db.get_random_offers(1)
            if not existing_offers:
                log.info("📦 Generating initial offers...")
                offers = self.offer_generator.generate_offers(30)
                for offer in offers:
                    self.db.add_offer(offer)
                log.info(f"✅ Generated {len(offers)} initial offers")
            
            # Create application
            self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            
            # Add handlers
            self.app.add_handler(CommandHandler("start", self.start_command))
            self.app.add_handler(CommandHandler("referral", self.referral_command))
            self.app.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
            self.app.add_handler(CommandHandler("help", self.help_command))
            
            # Add callback query handler
            from telegram.ext import CallbackQueryHandler
            self.app.add_handler(CallbackQueryHandler(self.handle_callback_query))
            
            # Schedule posts every 4 hours (only if job queue is available)
            if self.app.job_queue:
                self.app.job_queue.run_repeating(
                    self.scheduled_posts,
                    interval=14400,  # 4 hours in seconds
                    first=60  # Start after 1 minute
                )
                log.info("🔄 Scheduled posts every 4 hours")
            else:
                log.warning("⚠️ JobQueue not available, scheduled posts disabled")
            
            log.info("✅ LuxuryTrendBot started successfully!")
            log.info("🔄 Scheduled posts every 4 hours")
            log.info("💎 Referral system active")
            
            # Run the bot
            self.app.run_polling(drop_pending_updates=True)
            
        except Exception as e:
            log.error(f"❌ Failed to start LuxuryTrendBot: {e}")
            raise

def main():
    """Main function"""
    try:
        log.info("🔥 Initializing LuxuryTrendBot (Simplified)...")
        bot = LuxuryTrendBot()
        bot.start_bot()
    except KeyboardInterrupt:
        log.info("🛑 Bot stopped by user")
    except Exception as e:
        log.error(f"❌ Bot crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
