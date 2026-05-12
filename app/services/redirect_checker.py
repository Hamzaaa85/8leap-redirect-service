from dataclasses import dataclass
from urllib.parse import urljoin

import httpx


REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


@dataclass
class RedirectCheckOutcome:
    redirect_status_code: int | None
    redirect_location: str | None
    target_status_code: int | None
    passed: bool
    failure_type: str | None
    error_message: str | None


def normalize_location(original_url: str, location: str | None) -> str | None:
    if location is None:
        return None

    return urljoin(original_url, location)


async def request_without_following_redirects(
    client: httpx.AsyncClient,
    url: str,
    user_agent: str,
) -> tuple[int | None, str | None, str | None]:
    try:
        response = await client.get(
            url,
            headers={"User-Agent": user_agent},
            follow_redirects=False,
        )
        return (
            response.status_code,
            normalize_location(url, response.headers.get("Location")),
            None,
        )
    except httpx.TimeoutException as exc:
        return None, None, f"Timeout: {exc}"
    except httpx.HTTPError as exc:
        return None, None, str(exc)


async def check_redirect_result(
    *,
    original_url: str,
    expected_url: str,
    user_agent: str,
    timeout_seconds: int,
) -> RedirectCheckOutcome:
    timeout = httpx.Timeout(timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout) as client:
        redirect_status_code, redirect_location, redirect_error = (
            await request_without_following_redirects(
                client,
                original_url,
                user_agent,
            )
        )

        if redirect_error:
            return RedirectCheckOutcome(
                redirect_status_code=redirect_status_code,
                redirect_location=redirect_location,
                target_status_code=None,
                passed=False,
                failure_type="redirect_request_error",
                error_message=redirect_error,
            )

        if redirect_status_code not in REDIRECT_STATUS_CODES:
            return RedirectCheckOutcome(
                redirect_status_code=redirect_status_code,
                redirect_location=redirect_location,
                target_status_code=None,
                passed=False,
                failure_type="no_redirect",
                error_message=f"Expected redirect status, got {redirect_status_code}",
            )

        if redirect_location != expected_url:
            return RedirectCheckOutcome(
                redirect_status_code=redirect_status_code,
                redirect_location=redirect_location,
                target_status_code=None,
                passed=False,
                failure_type="wrong_location",
                error_message=(
                    f"Expected Location {expected_url}, got {redirect_location}"
                ),
            )

        target_status_code, _target_location, target_error = (
            await request_without_following_redirects(
                client,
                expected_url,
                user_agent,
            )
        )

        if target_error:
            return RedirectCheckOutcome(
                redirect_status_code=redirect_status_code,
                redirect_location=redirect_location,
                target_status_code=target_status_code,
                passed=False,
                failure_type="target_request_error",
                error_message=target_error,
            )

        if target_status_code != 200:
            return RedirectCheckOutcome(
                redirect_status_code=redirect_status_code,
                redirect_location=redirect_location,
                target_status_code=target_status_code,
                passed=False,
                failure_type="target_not_200",
                error_message=f"Expected target status 200, got {target_status_code}",
            )

        return RedirectCheckOutcome(
            redirect_status_code=redirect_status_code,
            redirect_location=redirect_location,
            target_status_code=target_status_code,
            passed=True,
            failure_type=None,
            error_message=None,
        )

