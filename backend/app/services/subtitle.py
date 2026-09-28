"""
字幕解析服务

把不同来源的字幕文本统一成 TranscriptCue 列表：
- SRT  （`.srt`，SubRip）
- WebVTT（`.vtt`，YouTube / B站导出常见）

不引入第三方字幕库：两种格式足够简单，自研解析器可控且便于做「滚动字幕去重」。

处理流水线：
    parse → 时间戳归一到毫秒 → 剥离内联标签 → 滚动去重 → 按时间排序重排 seq
"""

import html as html_lib
import re
from typing import Dict, List, Optional, Tuple

from app.models.learning import TranscriptSource
from app.utils.logger import logger

# 支持 00:01:02.345 / 01:02.345 / 00:01:02,345（SRT 用逗号）
_TIME_RE = re.compile(
    r"^(?:(\d{1,3}):)?([0-5]?\d):([0-5]\d)[.,](\d{1,3})$"
)

# SRT / WebVTT 的时间轴行
_CUE_LINE_RE = re.compile(
    r"^(?P<start>[0-9:.]+(?:[.,]\d{1,3})?)\s*-->\s*(?P<end>[0-9:.]+(?:[.,]\d{1,3})?)(?P<settings>.*)$"
)

# WebVTT 内联标签：<c>、<00:00:01.000>、<v Speaker>、<b>/<i>/<u>、<lang en> 等
_INLINE_TAG_RE = re.compile(r"<[^>]*>")

# 只含时间轴分隔符与空白的行要跳过（防止把 VTT 的 NOTE/STYLE 块误当字幕）
_MAX_TEXT_LEN = 4000


def parse_timestamp(raw: str) -> int:
    """
    把字幕时间字符串解析为毫秒

    支持 HH:MM:SS.mmm、MM:SS.mmm、SS.mmm，分隔符点号或逗号均可。

    Args:
        raw: 形如 "01:02:03.456" 的时间字符串

    Returns:
        毫秒整数；解析失败返回 0
    """
    raw = raw.strip()
    match = _TIME_RE.match(raw)
    if not match:
        # 退化情况：只有秒 "12.345"
        if raw.replace(".", "", 1).replace(",", "", 1).isdigit():
            seconds = float(raw.replace(",", "."))
            return int(seconds * 1000)
        return 0

    hour_group, minute_group, second_group, ms_group = match.groups()
    hours = int(hour_group) if hour_group else 0
    minutes = int(minute_group)
    seconds = int(second_group)
    # "4" → 400ms，"04" → 40ms（右补齐三位）
    milliseconds = int(ms_group.ljust(3, "0"))
    return ((hours * 3600) + (minutes * 60) + seconds) * 1000 + milliseconds


def clean_inline_markup(text: str) -> str:
    """
    剥离 WebVTT 内联标签、解码 HTML 实体并压缩空白

    - WebVTT 自动字幕会插入 `<c>` 高亮标签与 `<00:00:01.000>` 时间戳游标；
    - 说话人切换的 `>>` 会被转义成 `&gt;&gt;`，需还原，否则正文里全是实体噪声。
    """
    text = _INLINE_TAG_RE.sub("", text)
    text = html_lib.unescape(text)
    # 全角空格统一为半角，避免搜索匹配失败
    text = text.replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def _split_cue_blocks(raw: str) -> List[str]:
    """按空行切分字幕块"""
    return re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n"))


def parse_subtitle(
    raw: str,
    language: str = "",
    source: str = TranscriptSource.PLATFORM,
) -> List[dict]:
    """
    解析字幕文本为 cue 字典列表

    Args:
        raw: 字幕文件正文
        language: 语言代码，写入每条 cue
        source: platform / manual

    Returns:
        [{"seq", "start_ms", "end_ms", "text", "language", "source"}, ...]
    """
    if not raw or not raw.strip():
        return []

    # 关键：**按时间轴行切分，而不是按空行切块**。
    # YouTube 自动字幕同一份文件里混用两种写法：
    #   a) 时间行 + 空行 + 文本（带 <c> 词级标签的长句）
    #   b) 时间行 + 文本（无空行，纯文本的定格帧）
    # 按空行切块会把 (a) 的时间行与文本拆到两个块里，导致整句被当成无效块丢弃。
    cues: List[dict] = []
    current: Optional[Dict[str, int]] = None
    text_lines: List[str] = []

    def flush() -> None:
        if current is None:
            return
        text = clean_inline_markup(" ".join(text_lines))
        if text:
            cues.append(
                {
                    "start_ms": current["start_ms"],
                    "end_ms": current["end_ms"],
                    "text": text[:_MAX_TEXT_LEN],
                    "language": language,
                    "source": source,
                }
            )

    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()

        match = _CUE_LINE_RE.match(stripped)
        if match:
            flush()
            start_ms = parse_timestamp(match.group("start"))
            end_ms = parse_timestamp(match.group("end"))
            if end_ms <= start_ms:
                end_ms = start_ms + 1000
            current = {"start_ms": start_ms, "end_ms": end_ms}
            text_lines = []
            continue

        # 时间轴行之前的内容是文件头（WEBVTT / Kind / Language），忽略
        if current is None:
            continue
        # 序号行、空行、块标记都不属于正文
        if stripped == "" or stripped.isdigit():
            continue
        if stripped.upper().startswith(("NOTE", "STYLE", "REGION")):
            continue

        text_lines.append(stripped)

    flush()
    return _dedupe_rolling(_sort_and_reindex(cues))


def _sort_and_reindex(cues: List[dict]) -> List[dict]:
    """按起始时间稳定排序并重排 seq，同时修正时间倒挂"""
    ordered = sorted(cues, key=lambda item: (item["start_ms"], item["end_ms"]))
    previous_end = 0
    for cue in ordered:
        # 字幕条目偶有时间倒挂（start 小于上一条 end），夹逼到可用区间
        if cue["start_ms"] < previous_end:
            cue["start_ms"] = previous_end
        if cue["end_ms"] <= cue["start_ms"]:
            cue["end_ms"] = cue["start_ms"] + 1000
        previous_end = cue["end_ms"]
    for index, cue in enumerate(ordered):
        cue["seq"] = index
    return ordered


def _dedupe_rolling(cues: List[dict]) -> List[dict]:
    """
    滚动字幕去重

    YouTube 自动字幕是「累积长句 + 紧随的 10ms 定格帧」成对出现的：

        00:00:00.160 --> 00:00:03.030  Are you ready to immerse yourself in
        00:00:03.030 --> 00:00:03.040  Are you ready to immerse yourself in   ← 定格帧
        00:00:03.040 --> 00:00:06.070  Are you ready to immerse yourself in
                                       English today? Today I am here with my ← 累积句
        00:00:06.070 --> 00:00:06.080  English today? Today I am here with my ← 定格帧

    即：长句是「上一条 + 新词」，紧跟的定格帧内容又恰好等于「刚增出来的那部分」。
    不去重的话约一半条目都是重复的。

    策略：以**上一条最终保留下来的文本**为基准（注意是去重后的增量，不是原始文本），
    - 完全相同   → 并入前一条，只延长时间（处理定格帧）
    - 以其为前缀 → 只保留增量部分
    """
    result: List[dict] = []
    previous_text = ""

    for cue in cues:
        text = cue["text"]

        if previous_text:
            if text == previous_text:
                # 定格帧：内容一致，并入前一条，不新增条目
                if result:
                    result[-1]["end_ms"] = max(result[-1]["end_ms"], cue["end_ms"])
                continue

            if text.startswith(previous_text):
                remainder = text[len(previous_text) :].strip()
                if not remainder:
                    if result:
                        result[-1]["end_ms"] = max(result[-1]["end_ms"], cue["end_ms"])
                    continue
                cue["text"] = remainder
                result.append(cue)
                # 关键：基准必须更新为「实际保留下来的增量文本」。
                # 若沿用原始整句，后续的定格帧（内容等于增量）就匹配不上，会被当成新条目保留。
                previous_text = remainder
                continue

        result.append(cue)
        previous_text = text

    return _sort_and_reindex(result)


def count_subtitle_cues(raw: str) -> Tuple[int, int]:
    """
    粗统计字幕条数与总时长（毫秒）

    用于入库前判断字幕质量，避免把 1~2 条的残缺字幕当作完整字幕写入。

    Returns:
        (cue_count, total_ms)
    """
    cues = parse_subtitle(raw, source=TranscriptSource.MANUAL)
    if not cues:
        return 0, 0
    return len(cues), cues[-1]["end_ms"]


def looks_like_subtitle(raw: str) -> bool:
    """判断文本是否像 SRT/VTT 字幕（手动上传时做前置校验）"""
    if not raw:
        return False
    head = raw.lstrip()[:200]
    has_webvtt = head.upper().startswith("WEBVTT")
    first_block = _split_cue_blocks(raw)[0] if raw.strip() else ""
    has_timeline = bool(_CUE_LINE_RE.search(first_block))
    return has_webvtt or has_timeline


def validate_manual_subtitle(raw: str) -> List[dict]:
    """
    校验并解析用户手动上传的字幕

    Raises:
        ValueError: 内容不是合法字幕或条数过少
    """
    if not looks_like_subtitle(raw):
        raise ValueError("文件内容不是有效的 SRT/VTT 字幕")

    cues = parse_subtitle(raw, source=TranscriptSource.MANUAL)
    if len(cues) < 2:
        raise ValueError("字幕内容过少（少于 2 条），请检查文件是否完整")

    logger.info(f"手动字幕解析成功，共 {len(cues)} 条")
    return cues
