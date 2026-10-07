"""The general Google search from load_img/find_product_pages.py, adapted as a driver.

The search and result-screening functions below are copied verbatim from the old parser (2026-10-01,
SHA-256 6b935c65cb3f03316191fd5e7eaf5679175e5155a35b01cb47108448ef7f119a); its Playwright launch settings
and existing profile path are kept by OldParserGoogleBrowser. Result links are
still untrusted and go through the production LG candidate validation.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import importlib.util
from urllib.parse import parse_qs, quote_plus, unquote, urlparse, urlsplit
import re

from .browser_runtime import BrowserFailure

OLD_PARSER_DIR = Path(__file__).resolve().parents[3] / "load_img" / "01_search_product_links" / "find_product_pages"
OLD_PROFILE_DIR = OLD_PARSER_DIR / ".global_google_profile"
OLD_SOURCE_FILE = OLD_PARSER_DIR / "find_product_pages.py"
OLD_SOURCE_SHA256 = "6b935c65cb3f03316191fd5e7eaf5679175e5155a35b01cb47108448ef7f119a"
_original_module = None


def original_search_function():
    """Use the literal audited source in this workspace when it is available."""
    global _original_module
    if not OLD_SOURCE_FILE.is_file():
        return google_general_search, "transferred_copy"
    if hashlib.sha256(OLD_SOURCE_FILE.read_bytes()).hexdigest() != OLD_SOURCE_SHA256:
        raise RuntimeError("old_parser_source_changed")
    if _original_module is None:
        spec = importlib.util.spec_from_file_location("stage54_3_original_find_product_pages", OLD_SOURCE_FILE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _original_module = module
    return _original_module.google_general_search, "original_file"


def original_candidate_function():
    _search, kind = original_search_function()
    return _original_module.official_product_candidate if kind == "original_file" else official_product_candidate


def clean_google_result_url(raw_url):
    url = (raw_url or "").strip()
    if not url:
        return ""
    if url.startswith("/url?") or ("google." in urlparse(url).netloc.lower() and "/url?" in url):
        query = parse_qs(urlparse(url).query)
        url = (query.get("q") or query.get("url") or [""])[0]
    return unquote(url).split("#", 1)[0].split("?", 1)[0].rstrip("/")


GLOBAL_MARKETPLACE_DOMAINS = (
    "ozon.ru", "wildberries.ru", "market.yandex.ru", "avito.ru",
    "aliexpress.com", "aliexpress.ru", "sbermegamarket.ru", "beru.ru",
    "goods.ru", "kaspi.kz", "satom.ru", "all.biz", "tiu.ru", "pulscen.ru",
    "flowwow.com", "aliexpress.us",
)


def google_general_search(page, query, timeout_ms=60000):
    """Run a plain (no site:) Google search in the given page and return organic result links."""
    search_url = f"https://www.google.com/search?q={quote_plus(query)}&hl=en"
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(1000)
    except Exception as e:
        print(f"    Google error: {e}")
        return []

    try:
        body_text = page.locator("body").inner_text(timeout=5000).lower()
        check_markers = (
            "unusual traffic", "необычный трафик", "not a robot",
            "не робот", "before you continue to google",
        )
        if any(marker in body_text for marker in check_markers):
            print("    Google check detected. Solve it in the opened browser (waiting up to 3 minutes).")
            for _ in range(180):
                page.wait_for_timeout(1000)
                current_text = page.locator("body").inner_text(timeout=5000).lower()
                if not any(marker in current_text for marker in check_markers):
                    page.wait_for_timeout(1000)
                    print("    Google check passed.")
                    break
            else:
                print("    Google check was not solved in time.")
                return []
    except Exception:
        pass

    try:
        links = page.locator("a[href]").evaluate_all(
            "(items) => items.map(a => ({href: a.href || '', text: (a.innerText || '').trim()}))"
        )
    except Exception:
        links = []

    exclude_domains = (
        "google.", "youtube.com", "webcache.googleusercontent.com",
    ) + GLOBAL_MARKETPLACE_DOMAINS
    exclude_patterns = (
        "/support/", "/downloads/", "/warranty/",
        "/contact/", "/about/", "/news/", "/blog/",
    )

    results = []
    seen = set()
    for item in links:
        url = clean_google_result_url(item.get("href"))
        if not url or url in seen:
            continue
        host = urlparse(url).netloc.lower()
        if not host or any(d in host for d in exclude_domains):
            continue
        if any(p in url.lower() for p in exclude_patterns):
            continue
        seen.add(url)
        results.append((url, item.get("text", "")))
    return results


# Original result screening helpers, copied verbatim for standalone deployment.

def normalize_text(text):
    if not text:
        return ""
    text = text.lower()
    text = text.replace("\u0451", "\u0435")
    text = re.sub(r"[^a-z0-9\u0430-\u044f]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_model_keywords(model, brand=None):
    """Keywords from model: type, size, weight, color, etc."""
    if not model:
        return []
    model_norm = normalize_text(model)
    brand_norm = normalize_text(brand or "")
    tokens = model_norm.split()
    stop = {
        "\u0434\u043b\u044f", "\u0438", "\u0432", "\u043d\u0430", "\u0441", "\u043f\u043e", "\u0438\u0437", "\u0431\u0435\u0437",
        "\u0446\u0432\u0435\u0442", "\u0446\u0432\u0435\u0442\u0430", "\u0446\u0432\u0435\u0442\u043e\u043c", "\u043d\u043e\u043c\u0435\u0440", "\u0430\u0440\u0442", "\u0430\u0440\u0442\u0438\u043a\u0443\u043b",
        "\u043c\u043c", "\u0441\u043c", "\u043c", "\u0433", "\u0433\u0440", "\u043a\u0433"
    }
    keywords = []
    for t in tokens:
        if t in stop:
            continue
        if brand_norm and t == brand_norm:
            continue
        if len(t) < 2 and not any(ch.isdigit() for ch in t):
            continue
        keywords.append(t)
    return keywords


def url_belongs_to_domain(url, domain):
    """True only for the domain itself or one of its real subdomains."""
    if not url or not domain:
        return False
    host = urlparse(url).netloc.lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    domain = domain.lower().removeprefix("www.")
    return host == domain or host.endswith(f".{domain}")


GLOBAL_CATALOG_GENERIC_SEGMENTS = {
    "catalog", "category", "categories", "collection", "collections",
    "shop", "search", "list", "products", "product", "tags", "tag",
    "brand", "brands", "vendor", "vendors",
}


GLOBAL_CATALOG_TEXT_MARKERS = (
    "все товары", "результаты поиска",
)


def is_global_catalog_like(url, text):
    """
    Heuristic: true for category/catalog/listing pages rather than a single
    product page. Many official store sites put every product under a
    '/catalog/...' path, so only the *last* path segment (or an explicit
    pagination marker) is checked, not the presence of the word anywhere in
    the URL.
    """
    low_text = (text or "").lower()
    if any(word in low_text for word in GLOBAL_CATALOG_TEXT_MARKERS):
        return True

    parsed = urlparse(url)
    if re.search(r"(?:^|[?&])(?:page|p|pagen_?\d*)=", parsed.query.lower()):
        return True
    if "/page/" in parsed.path.lower():
        return True

    path = (parsed.path or "").strip("/")
    if not path:
        return False
    last_segment = path.split("/")[-1].lower()
    return last_segment in GLOBAL_CATALOG_GENERIC_SEGMENTS


def is_global_homepage_like(url):
    """Heuristic: true for the site's root/homepage (or a bare locale prefix), not a product page."""
    path = (urlparse(url).path or "").strip("/")
    if not path:
        return True
    segments = [s for s in path.split("/") if s]
    return all(len(s) <= 3 for s in segments)


def global_model_identifier(model, brand=None):
    """Take the model code from a longer product description when possible."""
    tokens = extract_model_keywords(model, brand=brand)
    numbered = [i for i, token in enumerate(tokens) if any(ch.isdigit() for ch in token)]
    if not numbered:
        return " ".join(tokens)
    first = numbered[0]
    if first and len(tokens[first - 1]) >= 3 and tokens[first - 1].isascii():
        first -= 1
    return " ".join(tokens[first:])


def global_exact_identifier_in(value, text):
    """Match complete code tokens across spaces, hyphens and URL separators."""
    tokens = normalize_text(value).split()
    if not tokens:
        return False
    pattern = r"(?<![a-z0-9а-я])" + r"[^a-z0-9а-я]*".join(map(re.escape, tokens)) + r"(?![a-z0-9а-я])"
    return bool(re.search(pattern, unquote(text or "").lower().replace("ё", "е")))


def official_product_candidate(url, title, domain, brand, model, article):
    """Accept a product URL only when its result names the exact model code."""
    if not url_belongs_to_domain(url, domain):
        return False
    if is_global_homepage_like(url) or is_global_catalog_like(url, title):
        return False
    # Search URLs often repeat the query in their parameters. Only the result
    # title and page path can establish that this is the requested product.
    haystack = f"{title} {urlparse(url).path}"
    model_identifier = global_model_identifier(model, brand=brand)
    if model_identifier and any(ch.isdigit() for ch in model_identifier):
        return (
            global_exact_identifier_in(model_identifier, haystack)
            or bool(article and global_exact_identifier_in(article, haystack))
        )
    if article:
        return global_exact_identifier_in(article, haystack)
    return global_exact_identifier_in(model_identifier, haystack)

class OldParserGoogleBrowser:
    """Playwright driver with the old parser's exact browser/profile setup."""

    def __init__(self, profile_dir: Path = OLD_PROFILE_DIR, playwright_factory=None):
        self.profile_dir = Path(profile_dir)
        self.playwright_factory = playwright_factory
        self.playwright = None
        self.context = None
        self.page = None
        self.rate_limit_url = ""
        self.last_status = None
        self.search_function = google_general_search
        self.candidate_function = official_product_candidate
        self.source_kind = "transferred_copy"
        self.counts = {"navigations": 0, "network_requests": 0, "blocked_requests": 0}

    def start(self):
        if not (self.profile_dir / "Default").is_dir():
            raise BrowserFailure("legacy_profile_missing", self.counts)
        if self.profile_dir.resolve() == OLD_PROFILE_DIR.resolve():
            self.search_function, self.source_kind = original_search_function()
            self.candidate_function = original_candidate_function()
        self.counts["old_parser_source"] = self.source_kind
        if self.playwright_factory is None:
            from playwright.sync_api import sync_playwright
            self.playwright_factory = sync_playwright
        self.playwright = self.playwright_factory().start()
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                str(self.profile_dir),
                headless=False,
                viewport={"width": 1440, "height": 1200},
                args=["--disable-blink-features=AutomationControlled"],
            )
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.page.on("response", self._response)
        except Exception:
            self.close()
            raise
        return {"counts": dict(self.counts)}

    def _response(self, response):
        if response.request.is_navigation_request() and response.request.frame == self.page.main_frame:
            self.last_status = response.status
            if response.status == 429:
                self.rate_limit_url = response.url

    def call(self, command: str, **args):
        if command == "close":
            self.close()
            return {"closed": True}
        if command != "goto" or self.page is None:
            raise BrowserFailure("interaction_blocked", self.counts)
        url = args.get("url", "")
        parsed = urlsplit(url)
        query = parse_qs(parsed.query).get("q", [""])[0]
        site_match = re.match(r"site:([A-Za-z0-9.-]+)\s", query)
        site = site_match.group(1).casefold() if site_match else ""
        hosts = args.get("search_result_hosts") or ["www.lg.com"]
        admitted_site = bool(site and any(host == site or host.endswith("." + site) for host in hosts))
        if parsed.scheme != "https" or parsed.hostname != "www.google.com" or parsed.path != "/search" or not admitted_site:
            raise BrowserFailure("interaction_blocked", self.counts)
        self.rate_limit_url = ""
        self.last_status = None
        self.counts["navigations"] += 1
        self.counts["old_parser_called"] = True
        links = self.search_function(self.page, query)
        self.counts["old_parser_completed"] = True
        if self.rate_limit_url:
            raise BrowserFailure("rate_limited", dict(self.counts, rate_limit_url=self.rate_limit_url))
        if "/sorry/" in self.page.url:
            raise BrowserFailure("challenge_detected", self.counts)
        match = re.fullmatch(r'site:[A-Za-z0-9.-]+\s+"([^"]+)"', query)
        fragments = []
        for link, title in links:
            old_candidate = (self.candidate_function(link, title, site, "LG" if site == "lg.com" else "", "", match.group(1))
                             if match and self.candidate_function is not None else None)
            fragments.append({"type": "result_link", "url": link, "title": title,
                              "snippet": "", "old_parser_candidate": old_candidate})
        return {"url": self.page.url, "projection": {"fragments": fragments},
                "counts": dict(self.counts), "javascript_errors": 0,
                "old_parser_source": self.source_kind}

    def close(self):
        if self.context is not None:
            self.context.close()
            self.context = None
        if self.playwright is not None:
            self.playwright.stop()
            self.playwright = None
        self.page = None
