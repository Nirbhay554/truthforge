"""
Bright Data API Client — shared module for all engines.
Handles SERP API, Web Unlocker, and Scraper API calls.
"""

import os
import httpx
from typing import Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


class BrightDataClient:
    """Unified client for all Bright Data services."""

    def __init__(self):
        self.api_key = os.getenv("BRIGHT_DATA_API_KEY")
        self.serp_url = os.getenv("BRIGHT_DATA_SERP_URL", "https://api.brightdata.com/request")
        self.unlocker_url = os.getenv("BRIGHT_DATA_UNLOCKER_URL", "https://api.brightdata.com/request")
        self.zone_serp = os.getenv("BRIGHT_DATA_ZONE_SERP", "serp_api1")
        self.zone_unlocker = os.getenv("BRIGHT_DATA_ZONE_UNLOCKER", "scraping_browser1")
        self.browser_ws = os.getenv("BRIGHT_DATA_BROWSER_WS")

        if not self.api_key or "your_bright_data_token_here" in self.api_key:
            logger.warning("BRIGHT_DATA_API_KEY not configured in environment.")

    async def fetch_page_with_browser(self, url: str) -> str:
        """Fetch full JS-rendered page via Bright Data Scraping Browser over CDP."""
        if not self.browser_ws or "**********" in self.browser_ws or "your_password" in self.browser_ws:
            return ""
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(self.browser_ws)
                page = await browser.new_page()
                await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                content = await page.content()
                await browser.close()
                logger.info(f"Bright Data Scraping Browser fetched: {url} ({len(content)} chars)")
                return content
        except Exception as e:
            logger.warning(f"Bright Data Scraping Browser failed for {url}: {e}")
            return ""

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=6))
    async def search_serp(self, query: str, engine: str = "google") -> str:
        """
        Search Google/Bing via Bright Data SERP API.
        Returns raw HTML results.
        """
        if not self.api_key or "your_bright_data_token_here" in self.api_key:
            return ""
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "zone": self.zone_serp,
            "url": search_url,
            "format": "raw",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.serp_url, headers=headers, json=payload)
                if response.status_code == 400:
                    logger.warning(f"Bright Data zone '{self.zone_serp}' not configured: {response.text.strip()}")
                    return ""
                response.raise_for_status()
                logger.info(f"SERP search complete: '{query}' ({len(response.text)} chars)")
                return response.text
        except Exception as e:
            logger.warning(f"SERP search unavailable for '{query}': {e}")
            return ""

    async def unlock_url(self, url: str) -> str:
        """
        Fetch any URL via Bright Data Web Unlocker or Scraping Browser.
        Bypasses bot detection, CAPTCHAs, and geo-blocks.
        """
        if not self.api_key or "your_bright_data_token_here" in self.api_key:
            return ""

        # Try Scraping Browser CDP if configured
        if self.browser_ws and "**********" not in self.browser_ws:
            browser_html = await self.fetch_page_with_browser(url)
            if browser_html:
                return browser_html
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "zone": self.zone_unlocker,
            "url": url,
            "format": "raw",
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(self.unlocker_url, headers=headers, json=payload)
                if response.status_code == 400:
                    logger.warning(f"Bright Data zone '{self.zone_unlocker}' not configured: {response.text.strip()}")
                    return ""
                response.raise_for_status()
                logger.info(f"Web Unlocker fetched: {url} ({len(response.text)} chars)")
                return response.text
        except Exception as e:
            logger.warning(f"Web Unlocker unavailable for {url}: {e}")
            return ""

    async def search_news(self, company_name: str, keywords: Optional[str] = None) -> str:
        """Search for company news."""
        query = f"{company_name} news"
        if keywords:
            query += f" {keywords}"
        return await self.search_serp(query)

    async def search_funding(self, company_name: str) -> str:
        """Search for funding/fundraising signals."""
        query = f"{company_name} funding round investment Series"
        return await self.search_serp(query)

    async def search_hiring(self, company_name: str) -> str:
        """Search for hiring/job signals."""
        query = f"{company_name} hiring jobs careers"
        return await self.search_serp(query)

    async def search_executive(self, company_name: str) -> str:
        """Search for executive changes."""
        query = f"{company_name} CEO CFO appointed new hire"
        return await self.search_serp(query)

    async def search_linkedin_jobs(self, company_name: str) -> str:
        """Search LinkedIn job postings via SERP API (fast)."""
        query = f"site:linkedin.com/jobs {company_name} hiring"
        return await self.search_serp(query)

    async def search_jobs(self, company_name: str, source: str) -> str:
        """Search job listings from a specific source via SERP API."""
        queries = {
            "linkedin":  f"site:linkedin.com/jobs {company_name}",
            "indeed":    f"site:indeed.com {company_name} jobs OR internship OR research",
            "glassdoor": f"site:glassdoor.com {company_name} jobs OR internship",
            "careers":   f"{company_name} careers jobs internship research entry level apply",
        }
        return await self.search_serp(queries.get(source, f"{company_name} jobs"))

    async def search_esg(self, company_name: str) -> str:
        """Search for ESG/sustainability claims."""
        query = f"{company_name} ESG sustainability carbon neutral report"
        return await self.search_serp(query)


bright_data = BrightDataClient()