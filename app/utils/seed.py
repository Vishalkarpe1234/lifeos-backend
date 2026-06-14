from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.core.config import settings
from app.models.user import User
from app.models.profile import Profile
from app.models.settings import AppSettings, Widget
import logging

logger = logging.getLogger(__name__)


async def seed_initial_data():
    async with AsyncSessionLocal() as db:
        try:
            existing = (await db.execute(select(User).where(User.email == settings.ADMIN_EMAIL))).scalar_one_or_none()
            if not existing:
                admin = User(
                    email=settings.ADMIN_EMAIL,
                    hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                    is_admin=True,
                    is_active=True,
                )
                db.add(admin)
                await db.flush()

                profile = Profile(
                    user_id=admin.id,
                    full_name="Vishal Karpe",
                    title="Assistant Professor | Developer | Researcher",
                    tagline="One App. One Life. Everything Connected.",
                    bio="Passionate educator and researcher at LJ University, pursuing PhD in Computer Applications. Expert in web development, machine learning, and data science.",
                    location="Pune, Maharashtra",
                    city="Pune",
                    state="Maharashtra",
                    country="India",
                    phone="+91 9130931719",
                    email_public="karpevishal2712001@gmail.com",
                    linkedin_url="https://www.linkedin.com/in/vishal-karpe1719",
                    blog_url="karpevishal.blogspot.com",
                    github_username="karpevishal",
                    skills=["HTML", "CSS", "JavaScript", "PHP", "Python", "Machine Learning", "Data Science", "Cloud Computing", "MySQL", "AWS"],
                    languages=["Marathi", "Hindi", "English"],
                    education=[
                        {"degree": "PhD - Computer Application", "institution": "GLS University", "year_start": "2025", "year_end": "Present"},
                        {"degree": "Master in Computer Science (MCA)", "institution": "Pune University", "year_start": "2022", "year_end": "2024", "percentage": "87.95%"},
                        {"degree": "Bachelor of Computer Science (BCA)", "institution": "Pune University", "year_start": "2019", "year_end": "2022", "percentage": "83.59%"},
                    ],
                    experience=[
                        {
                            "title": "Assistant Professor",
                            "company": "LJ University (Lok Jagruti University)",
                            "location": "Ahmedabad, Gujarat",
                            "start_date": "Oct 2023",
                            "is_current": True,
                            "description": "Conducting lectures and practical sessions on programming, web development, and Machine learning. Guiding students on academic projects and research in emerging technologies.",
                        }
                    ],
                )
                db.add(profile)

                default_widgets = [
                    Widget(widget_type="clock", title="Clock", order_index=0, dashboard_section="top"),
                    Widget(widget_type="tasks_today", title="Today's Tasks", order_index=1, dashboard_section="main"),
                    Widget(widget_type="habits", title="Habits", order_index=2, dashboard_section="main"),
                    Widget(widget_type="research_stats", title="Research", order_index=3, dashboard_section="main"),
                    Widget(widget_type="finance_summary", title="Finance", order_index=4, dashboard_section="main"),
                    Widget(widget_type="daily_quote", title="Daily Quote", order_index=5, dashboard_section="main"),
                    Widget(widget_type="productivity_score", title="Productivity", order_index=6, dashboard_section="main"),
                ]
                for w in default_widgets:
                    db.add(w)

                default_settings = [
                    AppSettings(key="app_theme", value="dark", category="appearance"),
                    AppSettings(key="app_color_scheme", value="indigo", category="appearance"),
                    AppSettings(key="language", value="en", category="general"),
                    AppSettings(key="date_format", value="DD/MM/YYYY", category="general"),
                    AppSettings(key="currency", value="INR", category="finance"),
                    AppSettings(key="currency_symbol", value="₹", category="finance"),
                ]
                for s in default_settings:
                    db.add(s)

                await db.commit()
                logger.info(f"Admin user seeded: {settings.ADMIN_EMAIL}")
            else:
                logger.info("Admin user already exists, skipping seed")
        except Exception as e:
            await db.rollback()
            logger.error(f"Seed error: {e}")
