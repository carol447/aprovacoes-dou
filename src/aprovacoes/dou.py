from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen


BASE = "https://www.in.gov.br"


@dataclass(frozen=True)
class DouResult:
    title: str
    url: str
    published: str = ""


class _DouHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._link_text: list[str] = []
        self._article_depth = 0
        self._article_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "a":
            self._href = attributes.get("href") or ""
            self._link_text = []
        if self._article_depth and tag not in {"br", "img", "hr", "meta", "link", "input"}:
            self._article_depth += 1
        elif tag in {"div", "article", "main"} and "texto-dou" in classes:
            self._article_depth = 1
        if self._article_depth and tag in {"p", "br", "div", "li", "tr"}:
            self._article_text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join("".join(self._link_text).split())))
            self._href = ""
            self._link_text = []
        if self._article_depth:
            self._article_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._href:
            self._link_text.append(data)
        if self._article_depth:
            self._article_text.append(data)

    @property
    def article_text(self) -> str:
        text = "".join(self._article_text)
        text = re.sub(r"[ \t]+", " ", text)
        return re.sub(r"\n\s*\n+", "\n", text).strip()


def _get(url: str, timeout: int) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout) as response:
        content = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    return content.decode(charset, errors="replace")


def search_act(act_number: int, act_date: date, timeout: int = 45) -> list[DouResult]:
    query = quote_plus(f'"ATO Nº {act_number}"')
    exact_date = act_date.strftime("%d-%m-%Y")
    url = f"{BASE}/consulta/-/buscar/dou?q={query}&s=todos&exactDate={exact_date}"
    parser = _DouHtmlParser()
    parser.feed(_get(url, timeout))
    results: list[DouResult] = []
    seen: set[str] = set()
    for raw_href, title in parser.links:
        if "/web/dou/-/" not in raw_href:
            continue
        href = urljoin(BASE, raw_href)
        if not href or href in seen or not re.search(rf"\b{act_number}\b", title):
            continue
        seen.add(href)
        results.append(DouResult(title=title, url=href))
    return results


def download_article(url: str, timeout: int = 45) -> str:
    parser = _DouHtmlParser()
    parser.feed(_get(url, timeout))
    if not parser.article_text:
        raise ValueError("O texto da matéria não foi encontrado na página do DOU")
    return parser.article_text
