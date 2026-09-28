"""内置 RSS/Atom 解析插件脚本（种子进库，可被用户复制改造）。"""

BUILTIN_RSS_PLUGIN_ID = "builtin-rss-atom"
BUILTIN_RSS_PLUGIN_NAME = "RSS / Atom"
BUILTIN_RSS_PLUGIN_DESCRIPTION = (
    "解析标准 RSS 2.0 与 Atom 订阅源。"
    "正文优先取 content:encoded / content，否则用 description/summary。"
)

BUILTIN_RSS_SCRIPT = r'''
from __future__ import annotations

import re
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree as ET

from subscription.plugin_runtime.base import ParsePayload, ParsedArticle, SubscriptionParser

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "media": "http://search.yahoo.com/mrss/",
}


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    parts = [node.text or ""]
    for child in node:
        parts.append(ET.tostring(child, encoding="unicode"))
    parts.append(node.tail or "")
    return unescape("".join(parts)).strip()


def _child_text(parent: ET.Element, *names: str) -> str:
    for name in names:
        found = parent.find(name, _NS)
        if found is not None:
            value = _text(found)
            if value:
                return value
        # 无命名空间回退
        local = name.split("}")[-1] if "}" in name else name.split(":")[-1]
        for child in parent:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == local:
                value = _text(child)
                if value:
                    return value
    return ""


def _attr(parent: ET.Element, path: str, attr: str) -> str:
    node = parent.find(path, _NS)
    if node is None:
        local = path.split("}")[-1] if "}" in path else path.split(":")[-1]
        for child in parent:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == local:
                node = child
                break
    if node is None:
        return ""
    return (node.attrib.get(attr) or "").strip()


def _normalize_date(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        from datetime import datetime
        return datetime.fromisoformat(text).isoformat()
    except ValueError:
        return text


def _first_img(html: str) -> str | None:
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I)
    return match.group(1) if match else None


class RssAtomParser(SubscriptionParser):
    def parse(self, payload: ParsePayload) -> list[ParsedArticle]:
        body = (payload.body or "").strip()
        if not body:
            raise ValueError("订阅源响应为空")
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            raise ValueError(
                f"XML 解析失败（{exc}）。若正文被截断请重试；确认源返回的是完整 RSS/Atom。"
            ) from exc
        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        if tag == "feed":
            return self._atom(root)
        channel = root.find("channel")
        if channel is None:
            channel = root.find("{http://purl.org/rss/1.0/}channel")
        if channel is not None:
            return self._rss(channel)
        # 某些源直接是 rdf:RDF
        items = root.findall("item") or root.findall("{http://purl.org/rss/1.0/}item")
        if items:
            return [self._rss_item(item) for item in items]
        raise ValueError("无法识别的 RSS/Atom 文档")

    def _rss(self, channel: ET.Element) -> list[ParsedArticle]:
        items = channel.findall("item") or channel.findall("{http://purl.org/rss/1.0/}item")
        return [self._rss_item(item) for item in items]

    def _rss_item(self, item: ET.Element) -> ParsedArticle:
        title = _child_text(item, "title")
        link = _child_text(item, "link")
        guid = _child_text(item, "guid") or link or title
        content = (
            _child_text(item, "content:encoded", "{http://purl.org/rss/1.0/modules/content/}encoded")
            or _child_text(item, "description")
        )
        author = _child_text(item, "author", "dc:creator", "{http://purl.org/dc/elements/1.1/}creator")
        published = _normalize_date(_child_text(item, "pubDate", "dc:date"))
        cover = (
            _attr(item, "media:thumbnail", "url")
            or _attr(item, "media:content", "url")
            or _first_img(content)
        )
        return ParsedArticle(
            external_id=guid,
            title=title or "(无标题)",
            content=content,
            content_format="html",
            published_at=published,
            author=author,
            cover_url=cover,
            url=link or None,
        )

    def _atom(self, feed: ET.Element) -> list[ParsedArticle]:
        articles: list[ParsedArticle] = []
        for entry in feed.findall("atom:entry", _NS) or feed.findall(
            "{http://www.w3.org/2005/Atom}entry"
        ):
            title = _child_text(entry, "atom:title", "{http://www.w3.org/2005/Atom}title")
            ident = _child_text(entry, "atom:id", "{http://www.w3.org/2005/Atom}id")
            link = ""
            for node in entry.findall("atom:link", _NS) or entry.findall(
                "{http://www.w3.org/2005/Atom}link"
            ):
                rel = node.attrib.get("rel", "alternate")
                href = node.attrib.get("href", "")
                if rel in {"alternate", ""} and href:
                    link = href
                    break
                if not link and href:
                    link = href
            content = _child_text(
                entry,
                "atom:content",
                "{http://www.w3.org/2005/Atom}content",
                "atom:summary",
                "{http://www.w3.org/2005/Atom}summary",
            )
            author_node = entry.find("atom:author", _NS) or entry.find(
                "{http://www.w3.org/2005/Atom}author"
            )
            author = ""
            if author_node is not None:
                author = _child_text(
                    author_node, "atom:name", "{http://www.w3.org/2005/Atom}name"
                )
            published = _normalize_date(
                _child_text(
                    entry,
                    "atom:published",
                    "{http://www.w3.org/2005/Atom}published",
                    "atom:updated",
                    "{http://www.w3.org/2005/Atom}updated",
                )
            )
            articles.append(
                ParsedArticle(
                    external_id=ident or link or title,
                    title=title or "(无标题)",
                    content=content,
                    content_format="html",
                    published_at=published,
                    author=author,
                    cover_url=_first_img(content),
                    url=link or None,
                )
            )
        return articles
'''
