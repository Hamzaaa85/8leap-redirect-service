"""
AI bot redirect checker.

Mental model:
- Normal browser opens the original website URL, for example:
  https://besthive.co/about-us/
- AI bots/crawlers send a special HTTP User-Agent, for example:
  ChatGPT-User
- The website should detect that User-Agent and redirect the bot to the
  AiWeave markdown/AI-friendly page, for example:
  https://aiweave.app/besthive/about-us/

This script acts like those AI bots by setting the HTTP User-Agent header.
Then it checks whether each original URL redirects to the expected AiWeave URL.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse


# These are the bot names the backend/middleware is expected to detect.
# The script will test every URL once for each bot User-Agent below.
BOT_USER_AGENTS = [
    "OAI-SearchBot",
    "ChatGPT-User",
    "Claude-SearchBot",
    "PerplexityBot",
]


# AiWeave base stays same for every generated markdown/AI-friendly page.
AIWEAVE_BASE_URL = "https://aiweave.app"


# Add only original website URLs here.
# The expected AiWeave URL is generated automatically from the domain + path.
ORIGINAL_URLS = [
    "https://besthive.co",
    "https://besthive.co/who-are-we/",
    "https://besthive.co/about-us/",
    "https://karobaronline.ai/biz/al-huda-travel-islamabad"
]


# Redirect status codes:
# 301/308 = permanent redirect.
# 302/303/307 = temporary/other redirect styles.
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


# Network requests should not hang forever if a website is slow/down.
REQUEST_TIMEOUT_SECONDS = 20


@dataclass
class CheckResult:
    """One test result for one URL and one bot User-Agent."""

    original_url: str
    expected_url: str
    user_agent: str
    redirect_status_code: int | None
    redirect_location: str | None
    target_status_code: int | None
    redirect_error: str | None = None
    target_error: str | None = None

    @property
    def redirect_passed(self) -> bool:
        """First check: original URL should redirect to the expected AiWeave URL."""

        return (
            self.redirect_error is None
            and self.redirect_status_code in REDIRECT_STATUS_CODES
            and self.redirect_location == self.expected_url
        )

    @property
    def target_page_passed(self) -> bool:
        """Second check: the AiWeave URL should actually exist and return 200."""

        return self.target_error is None and self.target_status_code == 200

    @property
    def passed(self) -> bool:
        """Final pass means redirect is correct AND redirected page is live."""

        return self.redirect_passed and self.target_page_passed


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    Stop Python from automatically following redirects.

    Why?
    If Python follows the redirect automatically, we only see the final AiWeave
    page response. For this QA script we need to inspect the FIRST response from
    the original website and read its Location header.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_without_following_redirects(url: str, user_agent: str) -> tuple[int | None, str | None, str | None]:
    """
    Send one HTTP request with a fake bot User-Agent.

    Returns:
    - status_code: HTTP status from the original website.
    - location: redirect target from the Location header, if present.
    - error: network/error message, if request failed.
    """

    request = urllib.request.Request(
        url,
        headers={
            # This is the key line: here we pretend to be an AI bot.
            "User-Agent": user_agent,
        },
        # Use GET because some websites do not handle HEAD requests exactly the
        # same way as real bot/page requests.
        method="GET",
    )

    opener = urllib.request.build_opener(NoRedirectHandler)

    try:
        response = opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS)
        status_code = response.status
        location = response.headers.get("Location")
        return status_code, normalize_location(url, location), None
    except urllib.error.HTTPError as exc:
        # urllib raises HTTPError for redirects and HTTP errors like 404/500.
        # That is okay; the exception still contains status code and headers.
        status_code = exc.code
        location = exc.headers.get("Location")
        return status_code, normalize_location(url, location), None
    except urllib.error.URLError as exc:
        # DNS failure, timeout, SSL issue, connection refused, etc.
        return None, None, str(exc.reason)


def normalize_location(original_url: str, location: str | None) -> str | None:
    """
    Convert relative redirect locations into full URLs.

    Example:
    If server returns Location: /besthive/about-us/
    this helper can convert it into a full URL based on the original URL.
    """

    if location is None:
        return None

    return urljoin(original_url, location)


def build_expected_aiweave_url(original_url: str) -> str:
    """
    Generate expected AiWeave URL from the original website URL.

    Pattern:
    https://besthive.co/about-us/
    becomes
    https://aiweave.app/besthive/about-us/
    """

    parsed = urlparse(original_url)

    if parsed.hostname is None:
        raise ValueError(f"Invalid URL, hostname missing: {original_url}")

    # besthive.co -> besthive
    # www.besthive.co -> besthive
    domain_without_www = parsed.hostname.removeprefix("www.")
    domain_slug = domain_without_www.split(".")[0]

    # Empty path means homepage. Homepage should become /besthive/.
    original_path = parsed.path or "/"

    # Build a stable base like: https://aiweave.app/besthive/
    aiweave_site_base = f"{AIWEAVE_BASE_URL.rstrip('/')}/{domain_slug}/"

    # Attach the original path after the domain slug.
    return urljoin(aiweave_site_base, original_path.lstrip("/"))


def check_redirect(original_url: str, user_agent: str) -> CheckResult:
    """Run both checks: redirect correctness and AiWeave page existence."""

    expected_url = build_expected_aiweave_url(original_url)

    redirect_status_code, redirect_location, redirect_error = request_without_following_redirects(
        original_url,
        user_agent,
    )

    # The redirected AiWeave URL must also return 200.
    target_status_code, _target_location, target_error = request_without_following_redirects(
        expected_url,
        user_agent,
    )

    return CheckResult(
        original_url=original_url,
        expected_url=expected_url,
        user_agent=user_agent,
        redirect_status_code=redirect_status_code,
        redirect_location=redirect_location,
        target_status_code=target_status_code,
        redirect_error=redirect_error,
        target_error=target_error,
    )


def print_result(result: CheckResult) -> None:
    """Print a human-readable PASS/FAIL line for one check."""

    label = "PASS" if result.passed else "FAIL"

    print(f"\n[{label}] {result.user_agent}")
    print(f"Original: {result.original_url}")
    print(f"Expected: {result.expected_url}")

    if result.redirect_error:
        print(f"Redirect error: {result.redirect_error}")
    else:
        print(f"Redirect status:   {result.redirect_status_code}")
        print(f"Redirect Location: {result.redirect_location}")

    if result.target_error:
        print(f"Target page error: {result.target_error}")
    else:
        print(f"Target page status: {result.target_status_code}")


def main() -> int:
    """
    Run all checks.

    Exit code:
    - 0 means all redirects are correct and target pages return 200.
    - 1 means at least one redirect/page check failed.
    """

    results: list[CheckResult] = []

    for original_url in ORIGINAL_URLS:
        for user_agent in BOT_USER_AGENTS:
            result = check_redirect(original_url, user_agent)
            results.append(result)
            print_result(result)

    total = len(results)
    passed = sum(1 for result in results if result.passed)
    failed = total - passed

    print("\nSummary")
    print("-------")
    print(f"Total:  {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
