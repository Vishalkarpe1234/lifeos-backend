from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Any
from datetime import datetime


class SocialLinks(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    twitter: Optional[str] = None
    youtube: Optional[str] = None
    instagram: Optional[str] = None
    blog: Optional[str] = None
    website: Optional[str] = None


class EducationItem(BaseModel):
    degree: str
    institution: str
    year_start: Optional[str] = None
    year_end: Optional[str] = None
    percentage: Optional[str] = None
    description: Optional[str] = None


class ExperienceItem(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    description: Optional[str] = None
    achievements: List[str] = []


class ProfileBase(BaseModel):
    full_name: Optional[str] = None
    title: Optional[str] = None
    tagline: Optional[str] = None
    bio: Optional[str] = None
    introduction: Optional[str] = None
    phone: Optional[str] = None
    email_public: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    skills: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    social_links: Optional[dict] = None
    education: Optional[List[dict]] = None
    experience: Optional[List[dict]] = None
    achievements: Optional[List[str]] = None
    website: Optional[str] = None
    github_username: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    youtube_url: Optional[str] = None
    instagram_url: Optional[str] = None
    blog_url: Optional[str] = None


class ProfileUpdate(ProfileBase):
    pass


class ProfileResponse(ProfileBase):
    id: int
    user_id: int
    profile_photo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    resume_url: Optional[str] = None
    cv_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
