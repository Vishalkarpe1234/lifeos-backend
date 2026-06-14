from typing import Optional, AsyncGenerator
from app.core.config import settings


class AIService:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if not self._client:
            if settings.ANTHROPIC_API_KEY:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    async def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
    ) -> dict:
        client = self._get_client()
        if not client:
            raise RuntimeError("AI service not configured. Set ANTHROPIC_API_KEY in .env")

        kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await client.messages.create(**kwargs)
        return {
            "content": response.content[0].text,
            "model": response.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

    async def generate_lecture_plan(self, topic: str, subject: str, duration_minutes: int = 50) -> str:
        prompt = f"""Create a detailed lecture plan for:
Subject: {subject}
Topic: {topic}
Duration: {duration_minutes} minutes

Include: Learning objectives, topics outline, teaching methods, activities, assessment, summary.
Format as structured markdown."""
        result = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are an expert academic curriculum designer and educator.",
        )
        return result["content"]

    async def generate_mcqs(self, topic: str, count: int = 10, difficulty: str = "medium") -> str:
        prompt = f"""Generate {count} multiple choice questions on:
Topic: {topic}
Difficulty: {difficulty}

Format each question as:
Q: [question]
A) [option]
B) [option]
C) [option]
D) [option]
Answer: [letter]
Explanation: [brief explanation]"""
        result = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are an expert educator creating assessment questions.",
        )
        return result["content"]

    async def generate_research_summary(self, abstract: str, title: str) -> str:
        prompt = f"""Provide a comprehensive research summary for:
Title: {title}
Abstract: {abstract}

Include: Key contributions, methodology, findings, limitations, future work, research gap addressed."""
        result = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are an expert research analyst.",
        )
        return result["content"]

    async def generate_blog_post(self, topic: str, keywords: list[str], word_count: int = 800) -> str:
        prompt = f"""Write a professional blog post:
Topic: {topic}
Keywords: {', '.join(keywords)}
Target word count: {word_count}

Include: Compelling title, introduction, body with headings, conclusion, SEO-friendly structure."""
        result = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are an expert technical content writer.",
        )
        return result["content"]

    async def summarize_pdf_text(self, text: str, format: str = "bullet") -> str:
        prompt = f"""Summarize the following document in {format} format.
Extract: Key points, important findings, conclusions, actionable insights.

Document text:
{text[:8000]}"""
        result = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are an expert document analyst.",
        )
        return result["content"]

    async def smart_search(self, query: str, context: str) -> str:
        prompt = f"""Answer the following question using only the provided context.
If the answer is not in the context, say so clearly.

Context: {context}
Question: {query}"""
        result = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are a precise knowledge assistant.",
        )
        return result["content"]


ai_service = AIService()
