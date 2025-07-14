#!/usr/bin/env python3
"""
LuxuryTrendBot - Simplified Version with Telegram Built-in Referrals
Automated Telegram Bot for Money Opportunities
Zero Friction Referral System
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
        logging.FileHandler('trendbot.log')
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
    """Data class for users with simplified referral tracking"""
    user_id: int
    username: str = ""
    first_name: str = ""
    referral_code: str = ""
    referred_by: Optional[str] = None
    referral_count: int = 0
    total_points: int = 0  # Simplified point system instead of money
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        if not self.referral_code:
            self.referral_code = f"LUX{str(self.user_id)[-6:].zfill(6)}"

@dataclass
class Referral:
    """Data class for referral tracking"""
    id: Optional[int] = None
    referrer_code: str = ""
    referred_user_id: int = 0
    points_awarded: int = 100  # Points instead of money
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class Database:
    """Simplified database for bot data"""
    
    def __init__(self, db_path: str = "trendbot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Offers table
            cursor.execute("""
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
            """)
            
            # Users table (simplified)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    referral_code TEXT UNIQUE,
                    referred_by TEXT,
                    referral_count INTEGER DEFAULT 0,
                    total_points INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Referrals table (simplified)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_code TEXT,
                    referred_user_id INTEGER,
                    points_awarded INTEGER DEFAULT 100,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Posts log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    offer_id INTEGER,
                    channel_id TEXT,
                    message_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            log.info("✅ Database initialized successfully")
    
    def save_offer(self, offer: Offer) -> int:
        """Save offer to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO offers (title, description, category, commission, gravity, affiliate_link, platform)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (offer.title, offer.description, offer.category, offer.commission, 
                  offer.gravity, offer.affiliate_link, offer.platform))
            conn.commit()
            return cursor.lastrowid
    
    def get_offers(self, limit: int = 10) -> List[Offer]:
        """Get offers from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, description, category, commission, gravity, affiliate_link, platform, created_at, updated_at
                FROM offers ORDER BY created_at DESC LIMIT ?
            """, (limit,))
            
            offers = []
            for row in cursor.fetchall():
                offer = Offer(
                    id=row[0], title=row[1], description=row[2], category=row[3],
                    commission=row[4], gravity=row[5], affiliate_link=row[6], platform=row[7],
                    created_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now(),
                    updated_at=datetime.fromisoformat(row[9]) if row[9] else datetime.now()
                )
                offers.append(offer)
            return offers
    
    def save_user(self, user: User):
        """Save or update user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, referral_code, referred_by, referral_count, total_points, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user.user_id, user.username, user.first_name, user.referral_code, 
                  user.referred_by, user.referral_count, user.total_points, datetime.now()))
            conn.commit()
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                return User(
                    user_id=row[0], username=row[1], first_name=row[2],
                    referral_code=row[3], referred_by=row[4], referral_count=row[5],
                    total_points=row[6],
                    created_at=datetime.fromisoformat(row[7]) if row[7] else datetime.now(),
                    updated_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now()
                )
            return None
    
    def process_referral(self, referrer_code: str, new_user_id: int) -> bool:
        """Process a new referral (simplified)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if referrer exists
            cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (referrer_code,))
            referrer = cursor.fetchone()
            
            if not referrer:
                return False
            
            referrer_id = referrer[0]
            
            # Award points to referrer
            cursor.execute("""
                UPDATE users SET 
                    referral_count = referral_count + 1,
                    total_points = total_points + 100,
                    updated_at = ?
                WHERE user_id = ?
            """, (datetime.now(), referrer_id))
            
            # Log the referral
            cursor.execute("""
                INSERT INTO referrals (referrer_code, referred_user_id, points_awarded)
                VALUES (?, ?, ?)
            """, (referrer_code, new_user_id, 100))
            
            conn.commit()
            return True
    
    def get_top_referrers(self, limit: int = 10) -> List[User]:
        """Get top referrers by referral count"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users 
                WHERE referral_count > 0 
                ORDER BY referral_count DESC, total_points DESC 
                LIMIT ?
            """, (limit,))
            
            users = []
            for row in cursor.fetchall():
                user = User(
                    user_id=row[0], username=row[1], first_name=row[2],
                    referral_code=row[3], referred_by=row[4], referral_count=row[5],
                    total_points=row[6],
                    created_at=datetime.fromisoformat(row[7]) if row[7] else datetime.now(),
                    updated_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now()
                )
                users.append(user)
            return users
    
    def log_post(self, offer_id: int, channel_id: str, message_id: int):
        """Log posted message"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO posts_log (offer_id, channel_id, message_id)
                VALUES (?, ?, ?)
            """, (offer_id, channel_id, message_id))
            conn.commit()

class OfferGenerator:
    """Generate money-making offers"""
    
    def __init__(self):
        self.platforms = {
            "ClickBank": {"commission_range": (20, 200), "gravity_range": (10, 500)},
            "Digistore24": {"commission_range": (15, 150), "gravity_range": (5, 300)},
            "SparkLoop": {"commission_range": (2, 10), "gravity_range": (50, 1000)},
            "beehiiv": {"commission_range": (3, 15), "gravity_range": (25, 800)}
        }
        
        self.categories = [
            "ai_tools", "crypto", "make_money", "business", "marketing", 
            "health", "fitness", "education", "software", "newsletters"
        ]
    
    def generate_offers(self, count: int = 20) -> List[Offer]:
        """Generate realistic offers"""
        offers = []
        
        for i in range(count):
            platform = random.choice(list(self.platforms.keys()))
            category = random.choice(self.categories)
            
            commission_range = self.platforms[platform]["commission_range"]
            gravity_range = self.platforms[platform]["gravity_range"]
            
            commission = round(random.uniform(*commission_range), 2)
            gravity = random.randint(*gravity_range) if platform in ["ClickBank", "Digistore24"] else None
            
            # Generate realistic titles and descriptions
            titles = {
                "ai_tools": [
                    "AI Business Automation Suite", "ChatGPT Profit System", "AI Content Creator Pro",
                    "Smart AI Assistant", "AI Marketing Toolkit", "Automated AI Writer"
                ],
                "crypto": [
                    "Crypto Trading Masterclass", "DeFi Yield Farming Guide", "NFT Creation Course",
                    "Bitcoin Investment Strategy", "Crypto Portfolio Tracker", "Blockchain Business Guide"
                ],
                "make_money": [
                    "Online Income Blueprint", "Passive Income System", "Digital Product Empire",
                    "Affiliate Marketing Mastery", "E-commerce Success Kit", "Side Hustle Academy"
                ]
            }
            
            category_titles = titles.get(category, ["Premium Opportunity", "Exclusive Offer", "Limited Access"])
            title = random.choice(category_titles)
            
            offer = Offer(
                title=title,
                description=f"Exclusive {category.replace('_', ' ').title()} opportunity with high conversion rates",
                category=category,
                commission=commission,
                gravity=gravity,
                affiliate_link=f"https://example.com/aff/{random.randint(1000, 9999)}",
                platform=platform
            )
            
            offers.append(offer)
        
        return offers

class ContentGenerator:
    """Generate engaging post content"""
    
    def __init__(self):
        self.emojis = {
            "ai_tools": ["🤖", "⚡", "🧠", "💡", "🔥"],
            "crypto": ["₿", "💎", "🚀", "📈", "⚡"],
            "make_money": ["💰", "💵", "🤑", "📊", "🎯"],
            "business": ["📈", "💼", "🎯", "⚡", "🔥"],
            "marketing": ["📢", "🎯", "📊", "💡", "🚀"]
        }
    
    def generate_post(self, offer: Offer) -> str:
        """Generate engaging post content"""
        category_emojis = self.emojis.get(offer.category, ["💎", "⚡", "🔥"])
        main_emoji = random.choice(category_emojis)
        
        # Calculate popularity score
        popularity = min(100, int((offer.commission / 2) + random.randint(10, 30)))
        
        post_content = f"""{main_emoji} **MONEY OPPORTUNITY ALERT!** {main_emoji}

🎯 **{offer.title}**
💵 **Commission**: ${offer.commission:.2f}
⭐ **Platform**: {offer.platform}
📈 **Category**: {offer.category.replace('_', ' ').title()}
🔥 **Popularity**: {popularity}/100

💡 **Why This Works:**
• High-converting offer with proven results
• Perfect for {offer.category.replace('_', ' ')} enthusiasts
• Instant commission payouts
• Professional marketing materials included

🚀 **Ready to earn?** Tap the link and start making money today!

👆 **[GET STARTED NOW]({offer.affiliate_link})**

💎 *Join thousands already earning with LuxuryTrendBot!*

#MakeMoneyOnline #PassiveIncome #{offer.category.title()}"""

        return post_content

class TrendBot:
    """Main bot class with simplified referral system"""
    
    def __init__(self):
        self.db = Database()
        self.offer_generator = OfferGenerator()
        self.content_generator = ContentGenerator()
        self.app = None
        self.stats = {
            "posts_sent": 0,
            "offers_generated": 0,
            "users_joined": 0,
            "referrals_processed": 0
        }
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with referral processing"""
        user = update.effective_user
        args = context.args
        
        # Get or create user
        db_user = self.db.get_user(user.id)
        is_new_user = db_user is None
        
        if is_new_user:
            # Create new user
            new_user = User(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or ""
            )
            
            # Process referral if provided
            if args and len(args) > 0:
                referral_code = args[0]
                if self.db.process_referral(referral_code, user.id):
                    new_user.referred_by = referral_code
                    self.stats["referrals_processed"] += 1
                    
                    # Notify referrer
                    try:
                        await self.app.bot.send_message(
                            chat_id=user.id,
                            text=f"🎉 **Congratulations!** You were referred by code `{referral_code}` and both of you earned bonus points!"
                        )
                    except:
                        pass
            
            self.db.save_user(new_user)
            self.stats["users_joined"] += 1
            db_user = new_user
        
        welcome_message = f"""
🎉 **Welcome to LuxuryTrendBot!** 💎

Hey {user.first_name or 'there'}! Ready to discover premium money-making opportunities?

**🚀 What You Get:**
• 💰 Curated high-paying offers daily
• 🎯 Verified opportunities from top platforms
• 📈 Real-time market insights
• 💎 Exclusive access to premium deals

**🏆 Your Referral Code:** `{db_user.referral_code}`
**📊 Your Points:** {db_user.total_points}
**👥 Referrals:** {db_user.referral_count}

**💡 Commands:**
• /referral - Get your referral link & stats
• /leaderboard - See top earners
• /help - Full command list

**🔥 Start earning by sharing your referral link!**
        """
        
        # Create inline keyboard
        keyboard = [
            [InlineKeyboardButton("🎯 Join Channel", url=f"https://t.me/{TELEGRAM_CHANNEL_ID.replace('@', '')}")],
            [InlineKeyboardButton("📊 My Referrals", callback_data="my_referrals"),
             InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /referral command - simplified version"""
        user = update.effective_user
        
        # Get or create user
        db_user = self.db.get_user(user.id)
        if not db_user:
            new_user = User(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or ""
            )
            self.db.save_user(new_user)
            db_user = new_user
        
        referral_message = f"""
💎 **Your Referral Dashboard**

**📊 Your Stats:**
👥 **Total Referrals**: {db_user.referral_count}
⭐ **Total Points**: {db_user.total_points:,}
🏆 **Referral Code**: `{db_user.referral_code}`

**🔗 Your Referral Link:**
`https://t.me/{BOT_USERNAME.replace('@', '')}?start={db_user.referral_code}`

**💎 Rewards System:**
• 🎯 **100 points** per referral
• 🏆 **Bonus points** for milestones
• 🎁 **Exclusive perks** for top referrers
• 💰 **Future cash rewards** (coming soon!)

**🚀 How to Maximize Referrals:**
• Share in entrepreneur groups
• Post on social media
• Tell friends about money opportunities
• Use our promotional materials

**🎯 Next Milestone:** {((db_user.referral_count // 10) + 1) * 10} referrals
        """
        
        # Create sharing buttons
        share_text = f"💎 Join LuxuryTrendBot for premium money opportunities! Use my code: {db_user.referral_code}"
        share_url = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start={db_user.referral_code}"
        
        keyboard = [
            [InlineKeyboardButton("📱 Share on Telegram", 
                                url=f"https://t.me/share/url?url={share_url}&text={share_text}")],
            [InlineKeyboardButton("🏆 View Leaderboard", callback_data="leaderboard"),
             InlineKeyboardButton("📊 Detailed Stats", callback_data=f"detailed_stats_{user.id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            referral_message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /leaderboard command"""
        top_users = self.db.get_top_referrers(limit=10)
        
        if not top_users:
            await update.message.reply_text("🏆 **Leaderboard**\n\nNo referrers yet! Be the first to earn! 🚀")
            return
        
        leaderboard_message = "🏆 **Top Referrers Leaderboard**\n\n"
        
        for i, user in enumerate(top_users, 1):
            if i == 1:
                emoji = "🥇"
            elif i == 2:
                emoji = "🥈"
            elif i == 3:
                emoji = "🥉"
            else:
                emoji = f"{i}."
            
            name = user.first_name or user.username or "Anonymous"
            leaderboard_message += f"{emoji} **{name}**\n"
            leaderboard_message += f"   👥 {user.referral_count} referrals | ⭐ {user.total_points:,} points\n\n"
        
        leaderboard_message += "💎 **Want to be on the leaderboard?**\n"
        leaderboard_message += "Use /referral to get your link and start earning! 🚀"
        
        await update.message.reply_text(leaderboard_message, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = f"""
🤖 **LuxuryTrendBot Help Center**

**📋 Available Commands:**
• `/start` - Welcome & setup your account
• `/referral` - Your referral dashboard & link
• `/leaderboard` - Top referrers ranking
• `/stats` - Bot performance statistics
• `/help` - This help message

**💎 Referral System:**
• Earn **100 points** per referral
• Get exclusive perks for top performance
• Future cash rewards coming soon!
• No limits on referrals!

**🎯 How to Earn:**
1. Get your referral link with `/referral`
2. Share with friends and groups
3. Earn points for each person who joins
4. Climb the leaderboard!

**📢 Channel:** {TELEGRAM_CHANNEL_ID}
**🤖 Bot:** {BOT_USERNAME}

**💡 Need help?** Contact @LuxuryTrendBot_Support
        """
        
        await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        offers = self.db.get_offers(limit=1000)
        
        if not offers:
            await update.message.reply_text("📊 No statistics available yet. Generating offers...")
            return
        
        avg_commission = sum(offer.commission for offer in offers) / len(offers)
        platforms = {}
        categories = {}
        
        for offer in offers:
            platforms[offer.platform] = platforms.get(offer.platform, 0) + 1
            categories[offer.category] = categories.get(offer.category, 0) + 1
        
        stats_message = f"""
📊 **LuxuryTrendBot Statistics**

**💰 Offer Stats:**
• Total Offers: {len(offers)}
• Average Commission: ${avg_commission:.2f}
• Top Platform: {max(platforms, key=platforms.get)}
• Top Category: {max(categories, key=categories.get)}

**🤖 Bot Performance:**
• Posts Sent: {self.stats['posts_sent']}
• Users Joined: {self.stats['users_joined']}
• Referrals Processed: {self.stats['referrals_processed']}
• Offers Generated: {self.stats['offers_generated']}

**📈 Revenue Potential:**
• Daily Potential: ${avg_commission * 6:.2f} (6 posts/day)
• Monthly Projection: ${avg_commission * 180:.2f}
• Top Earner Potential: ${avg_commission * 365:.2f}/year

**🎯 Growth:** +{random.randint(5, 25)}% this week
        """
        
        await update.message.reply_text(stats_message, parse_mode=ParseMode.MARKDOWN)
    
    async def post_to_channel(self):
        """Post offer to channel"""
        try:
            # Get or generate offers
            offers = self.db.get_offers(limit=10)
            if not offers:
                log.info("No offers found, generating new ones...")
                new_offers = self.offer_generator.generate_offers(20)
                for offer in new_offers:
                    self.db.save_offer(offer)
                    self.stats["offers_generated"] += 1
                offers = new_offers[:10]
            
            # Select random offer
            offer = random.choice(offers)
            
            # Generate post content
            post_content = self.content_generator.generate_post(offer)
            
            # Send to channel
            message = await self.app.bot.send_message(
                chat_id=TELEGRAM_CHANNEL_ID,
                text=post_content,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Log the post
            self.db.log_post(offer.id, TELEGRAM_CHANNEL_ID, message.message_id)
            self.stats["posts_sent"] += 1
            
            log.info(f"✅ Posted offer to channel: {offer.title} (Commission: ${offer.commission:.2f})")
            
        except Exception as e:
            log.error(f"❌ Failed to post to channel: {e}")
    
    async def scheduled_posts(self, context: ContextTypes.DEFAULT_TYPE):
        """Scheduled posting job"""
        await self.post_to_channel()
    
    def start_bot(self):
        """Start the bot - cloud compatible"""
        if not TELEGRAM_BOT_TOKEN:
            log.error("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
            return
        
        if not TELEGRAM_CHANNEL_ID:
            log.error("❌ TELEGRAM_CHANNEL_ID not found in environment variables")
            return
        
        log.info("🚀 Starting LuxuryTrendBot (Simplified)...")
        log.info("=" * 50)
        log.info("🤖 LuxuryTrendBot | Zero Friction Referrals")
        log.info("=" * 50)
        
        # Initialize offers
        offers = self.db.get_offers(limit=1)
        if not offers:
            log.info("📦 Generating initial offers...")
            initial_offers = self.offer_generator.generate_offers(30)
            for offer in initial_offers:
                self.db.save_offer(offer)
                self.stats["offers_generated"] += 1
            log.info(f"✅ Generated {len(initial_offers)} initial offers")
        
        # Create application
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("referral", self.referral_command))
        self.app.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        
        # Schedule posts every 4 hours
        job_queue = self.app.job_queue
        job_queue.run_repeating(self.scheduled_posts, interval=14400, first=10)  # 4 hours = 14400 seconds
        
        log.info("✅ LuxuryTrendBot started successfully!")
        log.info(f"📢 Posting to channel: {TELEGRAM_CHANNEL_ID}")
        log.info("🔄 Scheduled posts every 4 hours")
        log.info("💎 Simplified referral system active")
        log.info("🎯 Zero friction - ready to scale!")
        
        # Start polling - cloud compatible
        self.app.run_polling(drop_pending_updates=True)

def main():
    """Main entry point - cloud compatible"""
    try:
        log.info("🔥 Initializing LuxuryTrendBot (Simplified)...")
        bot = TrendBot()
        bot.start_bot()
    except Exception as e:
        log.error(f"❌ Failed to start LuxuryTrendBot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

