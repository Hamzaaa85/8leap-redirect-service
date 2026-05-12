from urllib.parse import urljoin, urlparse


def get_domain_slug(website_domain: str) -> str:
    domain = website_domain.strip()
    if not domain:
        raise ValueError("Website domain is missing")

    if "://" in domain:
        parsed_domain = urlparse(domain)
        host = parsed_domain.hostname or ""
    else:
        host = domain.split("/")[0]

    host = host.lower().removeprefix("www.").strip()
    if not host:
        raise ValueError("Website domain hostname is missing")

    return host.split(".")[0]


def build_expected_aiweave_url(
    original_url: str,
    website_domain: str,
    aiweave_base_url: str,
) -> str:
    parsed_original = urlparse(original_url.strip())
    if parsed_original.scheme not in {"http", "https"}:
        raise ValueError("Original URL must include http:// or https://")
    if not parsed_original.hostname:
        raise ValueError("Original URL hostname is missing")

    domain_slug = get_domain_slug(website_domain)
    original_path = parsed_original.path or "/"

    aiweave_site_base = f"{aiweave_base_url.rstrip('/')}/{domain_slug}/"
    return urljoin(aiweave_site_base, original_path.lstrip("/"))
