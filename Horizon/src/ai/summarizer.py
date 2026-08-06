"""Daily summary generation — pure programmatic rendering."""

import html
import re
from typing import Dict, List, Optional
from urllib.parse import quote, urlsplit

from ..models import ContentItem


_CJK = r"[\u4e00-\u9fff\u3400-\u4dbf]"
_ASCII = r"[A-Za-z0-9]"
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()<>#!|])")
_MARKDOWN_BLOCK_START = re.compile(r"(?m)^( {0,3})(>|[-+] |\d+[.)] )")
_URL_SAFE_CHARS = ":/?#[]@!$&'*,;=~%+"


def _escape_markdown(value: object) -> str:
    """Render untrusted text literally while retaining its readable content."""
    escaped = html.escape(str(value), quote=True)
    escaped = _MARKDOWN_SPECIAL.sub(r"\\\1", escaped)
    return _MARKDOWN_BLOCK_START.sub(r"\1\\\2", escaped)


def _safe_url(value: object) -> Optional[str]:
    """Return an HTML/Markdown-safe HTTP(S) URL, or None for unsafe URLs."""
    raw = str(value).strip()
    if not raw or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        return None
    try:
        parsed = urlsplit(raw)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        parsed.port
    except (TypeError, ValueError):
        return None
    encoded = quote(raw, safe=_URL_SAFE_CHARS)
    return html.escape(encoded, quote=True)


def _pangu(text: str) -> str:
    """Insert a space between CJK and ASCII letters/digits (Pangu spacing)."""
    text = re.sub(rf"({_CJK})({_ASCII})", r"\1 \2", text)
    text = re.sub(rf"({_ASCII})({_CJK})", r"\1 \2", text)
    return text


LABELS = {
    "en": {
        "header": "Horizon Daily",
        "source": "Source",
        "background": "Background",
        "discussion": "Discussion",
        "references": "References",
        "tags": "Tags",
        "selected_items": "From {total} items, {selected} important content pieces were selected",
        "empty_analyzed": "Analyzed {total} items, but none met the importance threshold.",
        "empty_body": (
            "No significant developments today. This might indicate:\n"
            "- A quiet day in your tracked sources\n"
            "- The AI score threshold is too high\n"
            "- Your information sources need expansion\n\n"
            "Consider:\n"
            "1. Lowering the `ai_score_threshold` in config.json\n"
            "2. Adding more diverse information sources\n"
            "3. Checking if the AI model is working correctly\n"
        ),
    },
    "zh": {
        "header": "Horizon 每日速递",
        "source": "来源",
        "background": "背景",
        "discussion": "社区讨论",
        "references": "参考链接",
        "tags": "标签",
        "selected_items": "从 {total} 条内容中筛选出 {selected} 条重要资讯。",
        "empty_analyzed": "已分析 {total} 条内容，但没有达到重要性阈值的条目。",
        "empty_body": (
            "今日暂无重要动态，可能原因：\n"
            "- 今天关注的信息源较平静\n"
            "- AI 评分阈值设置过高\n"
            "- 信息源种类有待扩充\n\n"
            "建议：\n"
            "1. 在 config.json 中降低 `ai_score_threshold`\n"
            "2. 添加更多多样化的信息源\n"
            "3. 检查 AI 模型是否正常工作\n"
        ),
    },
}

# Section labels and display order for category-grouped output
SECTION_LABELS = {
    "en": {
        "energy": "🔋 Energy News",
        "ai-tech": "🤖 AI & Technology",
        "big-tech": "🏢 Big Tech Companies",
    },
    "zh": {
        "energy": "🔋 能源资讯",
        "ai-tech": "🤖 AI 科技",
        "big-tech": "🏢 大厂要闻",
    },
}
SECTION_ORDER = ["energy", "ai-tech", "big-tech"]


class DailySummarizer:
    """Generates daily Markdown summaries from pre-analyzed content items."""

    def __init__(self):
        pass

    async def generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate daily summary in Markdown format.

        Items are rendered in score-descending order (already sorted by orchestrator).

        Args:
            items: High-scoring content items (already enriched)
            date: Date string (YYYY-MM-DD)
            total_fetched: Total number of items fetched before filtering
            language: Output language, either "en" or "zh"

        Returns:
            str: Markdown formatted summary
        """
        labels = LABELS.get(language, LABELS["en"])

        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        header = (
            f"# {labels['header']} - {date}\n\n"
            f"> {labels['selected_items'].format(total=total_fetched, selected=len(items))}\n\n"
            "---\n\n"
        )

        # Group items by category
        section_labels = SECTION_LABELS.get(language, SECTION_LABELS["en"])
        grouped: Dict[str, List[ContentItem]] = {}
        for item in items:
            cat = item.metadata.get("category") or "other"
            grouped.setdefault(cat, []).append(item)

        # Sort each group by score descending
        for group_items in grouped.values():
            group_items.sort(key=lambda x: x.ai_score or 0, reverse=True)

        # Build TOC with sections
        toc_lines = []
        item_counter = 1
        flat_index: Dict[str, int] = {}  # item id -> global index
        for section_key in SECTION_ORDER:
            section_items = grouped.pop(section_key, [])
            if not section_items:
                continue
            section_name = section_labels.get(section_key, section_key)
            toc_lines.append(f"### {section_name}\n")
            for item in section_items:
                _t = item.metadata.get(f"title_{language}") or item.title
                t = _escape_markdown(_t)
                if language == "zh":
                    t = _pangu(t)
                score = item.ai_score or "?"
                toc_lines.append(f"{item_counter}. [{t}](#item-{item_counter}) \u2b50\ufe0f {score}/10")
                flat_index[item.id] = item_counter
                item_counter += 1
            toc_lines.append("")
        # Remaining categories (e.g. "other")
        for section_key, section_items in grouped.items():
            if not section_items:
                continue
            section_name = section_labels.get(section_key, f"\ud83d\udccc {section_key}")
            toc_lines.append(f"### {section_name}\n")
            for item in section_items:
                _t = item.metadata.get(f"title_{language}") or item.title
                t = _escape_markdown(_t)
                if language == "zh":
                    t = _pangu(t)
                score = item.ai_score or "?"
                toc_lines.append(f"{item_counter}. [{t}](#item-{item_counter}) \u2b50\ufe0f {score}/10")
                flat_index[item.id] = item_counter
                item_counter += 1
            toc_lines.append("")
        toc = "\n".join(toc_lines) + "\n---\n\n"

        # Render body with section headers
        body_parts: List[str] = []
        rendered_sections: Dict[str, List[ContentItem]] = {}
        for item in items:
            cat = item.metadata.get("category") or "other"
            rendered_sections.setdefault(cat, []).append(item)

        for section_key in SECTION_ORDER:
            section_items = rendered_sections.pop(section_key, [])
            if not section_items:
                continue
            section_name = section_labels.get(section_key, section_key)
            body_parts.append(f"## {section_name}\n\n")
            for item in section_items:
                idx = flat_index.get(item.id, 0)
                body_parts.append(self._format_item(item, labels, language, idx))
        for section_key, section_items in rendered_sections.items():
            if not section_items:
                continue
            section_name = section_labels.get(section_key, f"\ud83d\udccc {section_key}")
            body_parts.append(f"## {section_name}\n\n")
            for item in section_items:
                idx = flat_index.get(item.id, 0)
                body_parts.append(self._format_item(item, labels, language, idx))

        return header + toc + "".join(body_parts)

    async def generate_daily_brief_json(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "zh",
    ) -> dict:
        """Generate daily brief in JSON format for external API consumption.

        Returns a lightweight JSON-serializable dict suitable for "每日速递"
        display. Each item includes headline, tldr (one-line summary), and
        key metadata — no long-form content.
        """
        from datetime import datetime, timezone

        section_labels = SECTION_LABELS.get(language, SECTION_LABELS["en"])

        # Group items by category
        grouped: Dict[str, List[ContentItem]] = {}
        for item in items:
            cat = item.metadata.get("category") or "other"
            grouped.setdefault(cat, []).append(item)

        # Sort each group by score descending
        for group_items in grouped.values():
            group_items.sort(key=lambda x: x.ai_score or 0, reverse=True)

        # Build sections in configured order
        sections: list = []
        rank = 0
        for section_key in SECTION_ORDER:
            section_items = grouped.pop(section_key, [])
            if not section_items:
                continue
            section_name = section_labels.get(section_key, section_key)
            items_json = []
            for item in section_items:
                rank += 1
                items_json.append(self._format_brief_item(item, language, rank))
            sections.append({
                "key": section_key,
                "title": section_name,
                "items": items_json,
            })

        # Remaining categories (e.g. "other")
        for section_key, section_items in grouped.items():
            if not section_items:
                continue
            section_name = section_labels.get(section_key, f"\U0001f4cc {section_key}")
            items_json = []
            for item in section_items:
                rank += 1
                items_json.append(self._format_brief_item(item, language, rank))
            sections.append({
                "key": section_key,
                "title": section_name,
                "items": items_json,
            })

        return {
            "meta": {
                "date": date,
                "title": "Horizon 每日速递",
                "generated_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "total_fetched": total_fetched,
                "total_selected": len(items),
            },
            "sections": sections,
        }

    def _format_brief_item(
        self, item: ContentItem, language: str, rank: int
    ) -> dict:
        """Format a single ContentItem into a brief JSON object with full content."""
        meta = item.metadata

        headline = meta.get(f"title_{language}") or item.title

        # Full summary (not truncated)
        summary = (
            meta.get(f"detailed_summary_{language}")
            or meta.get("detailed_summary")
            or item.ai_summary
            or ""
        )

        # Background context
        background = (
            meta.get(f"background_{language}")
            or meta.get("background")
            or ""
        )

        # Community discussion text
        discussion = (
            meta.get(f"community_discussion_{language}")
            or meta.get("community_discussion")
            or ""
        )

        # Reference links
        references: list = []
        for source in meta.get("sources") or []:
            ref_title = source.get("title", "")
            ref_url = source.get("url", "")
            safe_ref_url = _safe_url(ref_url) if ref_url else None
            if safe_ref_url:
                references.append({
                    "title": ref_title,
                    "url": str(safe_ref_url),
                })
            elif ref_title:
                references.append({"title": ref_title})

        # Source name: prefer feed_name, fall back to author
        source_name = meta.get("feed_name") or item.author or "unknown"

        # Friendly publish date
        if item.published_at:
            if language == "zh":
                published = (
                    f"{item.published_at.month}月"
                    f"{item.published_at.day}日 "
                    f"{item.published_at:%H:%M}"
                )
            else:
                day = item.published_at.strftime("%d").lstrip("0")
                published = item.published_at.strftime(f"%b {day}, %H:%M")
        else:
            published = ""

        # Discussion URL (only present for HackerNews-style sources)
        discussion_url = None
        raw_disc = meta.get("discussion_url")
        if raw_disc:
            safe_disc = _safe_url(raw_disc)
            if safe_disc:
                discussion_url = str(safe_disc)

        result: dict = {
            "rank": rank,
            "headline": headline,
            "url": str(item.url),
            "tldr": self._extract_first_sentence(summary, language),
            "summary": summary,
            "source_type": item.source_type.value,
            "source_name": source_name,
            "published": published,
            "score": item.ai_score,
            "tags": item.ai_tags or [],
        }
        if background:
            result["background"] = background
        if discussion:
            result["discussion"] = discussion
        if references:
            result["references"] = references
        if discussion_url:
            result["discussion_url"] = discussion_url

        return result

    @staticmethod
    def _extract_first_sentence(text: str, language: str) -> str:
        """Extract the first sentence from text, capped at ~100 chars."""
        if not text:
            return ""

        if language == "zh":
            # Match up to and including first 。！？
            match = re.match(r"(.*?[。！？])", text)
            first = match.group(1) if match else text
            if len(first) > 100:
                # Cut at last sentence-ending char within limit
                truncated = first[:100]
                last_end = max(
                    truncated.rfind("。"),  # 。
                    truncated.rfind("！"),  # ！
                    truncated.rfind("？"),  # ？
                )
                if last_end > 10:
                    first = truncated[: last_end + 1]
                else:
                    first = truncated + "…"  # …
            return first

        # English: first sentence ending with . ! ? followed by space or end
        match = re.match(r"(.*?[.!?])(?:\s|$)", text)
        first = match.group(1) if match else text
        if len(first) > 200:
            first = first[:197] + "..."
        return first

    def generate_webhook_overview(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate a compact overview for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        if language == "zh":
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> 从 {total_fetched} 条内容中筛选出 {len(items)} 条重要资讯。\n\n"
                "下面会按新闻逐条发送详情，你可以只看感兴趣的标题。\n\n"
            )
        else:
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> Selected {len(items)} important items from {total_fetched} fetched items.\n\n"
                "Details will be sent item by item so you can read only the topics you care about.\n\n"
            )

        entries = []
        for i, item in enumerate(items, start=1):
            title = _escape_markdown(item.metadata.get(f"title_{language}") or item.title)
            if language == "zh":
                title = _pangu(title)
            score = item.ai_score or "?"
            url = _safe_url(item.url)
            title_link = f"[{title}]({url})" if url else title
            entries.append(f"{i}. {title_link} \u2b50\ufe0f {score}/10")

        return header + "\n".join(entries)

    def generate_webhook_item(
        self,
        item: ContentItem,
        language: str,
        index: int,
        total: int,
    ) -> str:
        """Generate one item message for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        prefix = f"第 {index}/{total} 条\n\n" if language == "zh" else f"Item {index}/{total}\n\n"
        return prefix + self._format_item(item, labels, language, index).rstrip("-\n ")

    def _format_item(self, item: ContentItem, labels: dict, language: str, index: int) -> str:
        """Format a single ContentItem into Markdown."""
        _title = item.metadata.get(f"title_{language}") or item.title
        title = _escape_markdown(_title)
        raw_url = str(item.url)
        url = _safe_url(raw_url)
        score = item.ai_score or "?"
        meta = item.metadata

        summary = (
            meta.get(f"detailed_summary_{language}")
            or meta.get("detailed_summary")
            or item.ai_summary
            or ""
        )
        background = meta.get(f"background_{language}") or meta.get("background") or ""
        discussion = (
            meta.get(f"community_discussion_{language}")
            or meta.get("community_discussion")
            or ""
        )

        summary = _escape_markdown(summary)
        background = _escape_markdown(background)
        discussion = _escape_markdown(discussion)

        if language == "zh":
            title = _pangu(title)
            summary = _pangu(summary)
            background = _pangu(background)
            discussion = _pangu(discussion)

        # Source line with parts joined by " · ", link appended at end
        source_type = item.source_type.value
        source_parts = [_escape_markdown(source_type)]
        if meta.get("subreddit"):
            source_parts.append(_escape_markdown(f"r/{meta['subreddit']}"))
        if meta.get("feed_name"):
            source_parts.append(_escape_markdown(meta["feed_name"]))
        else:
            source_parts.append(_escape_markdown(item.author or "unknown"))
        if item.published_at:
            if language == "zh":
                source_parts.append(
                    f"{item.published_at.month}月{item.published_at.day}日 "
                    f"{item.published_at:%H:%M}"
                )
            else:
                day = item.published_at.strftime("%d").lstrip("0")
                source_parts.append(item.published_at.strftime(f"%b {day}, %H:%M"))
        source_line = " \u00b7 ".join(source_parts)  # ·

        discussion_url = meta.get("discussion_url")
        if discussion_url:
            safe_discussion_url = _safe_url(discussion_url)
            if safe_discussion_url and str(discussion_url) != raw_url:
                source_line += f' · [{labels["discussion"]}]({safe_discussion_url})'

        title_link = f"[{title}]({url})" if url else title

        lines = [
            f'<a id="item-{index}"></a>',
            f"## {title_link} \u2b50\ufe0f {score}/10",  # ⭐️
            "",
            summary,
            "",
            source_line,
        ]

        if background:
            lines.append("")
            lines.append(f"**{labels['background']}**: {background}")

        sources = meta.get("sources") or []
        if sources:
            reference_items = []
            for source in sources:
                reference_title = html.escape(str(source.get("title", "")), quote=True)
                reference_url = _safe_url(source.get("url", ""))
                if reference_url:
                    reference_items.append(f'<li><a href="{reference_url}">{reference_title}</a></li>\n')
                else:
                    reference_items.append(f"<li>{reference_title}</li>\n")
            items_html = "".join(reference_items)
            lines += [
                "",
                f'<details><summary>{labels["references"]}</summary>\n<ul>\n{items_html}\n</ul>\n</details>',
            ]

        if discussion:
            lines.append("")
            lines.append(f"**{labels['discussion']}**: {discussion}")

        if item.ai_tags:
            tags_str = ", ".join([f"`#{_escape_markdown(t)}`" for t in item.ai_tags])
            lines.append("")
            lines.append(f"**{labels['tags']}**: {tags_str}")

        lines.append("")
        lines.append("---")

        return "\n".join(lines) + "\n\n"

    def _generate_empty_summary(self, date: str, total_fetched: int, labels: dict) -> str:
        """Generate summary when no high-scoring items were found."""
        return (
            f"# {labels['header']} - {date}\n\n"
            f"> {labels['empty_analyzed'].format(total=total_fetched)}\n\n"
            + labels["empty_body"]
        )
