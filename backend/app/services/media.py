"""
媒体抓取服务

职责：
1. 识别 URL 所属平台（YouTube / 哔哩哔哩），抽出平台视频 ID
2. 调用 yt-dlp Python API 抓取**元数据与字幕**（--skip-download，绝不下载视频本体）
3. 输出统一结构交给 LearningService 落库

设计要点：
- **不下载视频**：播放器走官方 iframe 嵌入，零存储成本、无版权风险。
- **字幕优先，没有也不算失败**：平台无字幕时返回空 cues，资源状态置为
  `no_subtitle`，仍可播放与计时，用户后续可手动上传 SRT/VTT。
- **抓取在线程池执行**：yt-dlp 是同步阻塞调用，必须在 worker 线程里跑，
  否则会卡死 uvicorn 事件循环。
"""

import asyncio
import copy
import os
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401 - Any/Tuple 供类型标注使用

from app.core.config import settings
from app.models.learning import ResourceSource, TranscriptSource
from app.services.subtitle import parse_subtitle
from app.utils.logger import logger


# B站 BV 号：BV + 10 位字母数字
_BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
# YouTube 视频 ID：11 位 base64 字符
_YT_ID_RE = re.compile(r"(?:v=|/shorts/|/embed/|/live/|youtu\.be/)([0-9A-Za-z_-]{11})")

# 提取好的 .srt / .vtt 字幕文件后缀优先级
_SUBTITLE_EXTS = (".vtt", ".srt")

# 单次最多抓取的语言轨道数。YouTube 对「翻译类自动字幕」限流（HTTP 429），
# 一次请求太多语言会整体失败，因此只取优先级最高的几条。
MAX_SUBTITLE_LANGS = 3


def _detect_js_runtime() -> Optional[str]:
    """
    探测可用的 JavaScript runtime

    新版 yt-dlp 解析 YouTube 依赖 JS runtime 完成 PO Token / n-parameter 签名。
    缺失时提取会降级，日志出现「No supported JavaScript runtime could be found」，
    直接后果是**自动字幕下载不到**（人工字幕不受影响）。
    """
    for name in ("node", "deno", "bun", "quickjs"):
        if shutil.which(name):
            return name
    return None


class _YtdlpLogger:
    """把 yt-dlp 的告警与错误接入项目日志，否则抓取失败时无从排查"""

    @staticmethod
    def debug(message: str) -> None:
        pass

    @staticmethod
    def info(message: str) -> None:
        pass

    @staticmethod
    def warning(message: str) -> None:
        logger.warning(f"[yt-dlp] {message}")

    @staticmethod
    def error(message: str) -> None:
        logger.error(f"[yt-dlp] {message}")


class MediaUnavailableError(Exception):
    """yt-dlp 未安装或抓取失败"""


def detect_platform(url: str) -> Tuple[str, Optional[str]]:
    """
    识别 URL 平台并抽取视频 ID

    Args:
        url: 用户粘贴的链接

    Returns:
        (platform, platform_id)；无法识别时 platform_id 为 None
    """
    raw = (url or "").strip()
    lowered = raw.lower()

    if "youtu.be" in lowered or "youtube.com" in lowered or "youtube-nocookie.com" in lowered:
        match = _YT_ID_RE.search(raw)
        return ResourceSource.YOUTUBE, match.group(1) if match else None

    if "bilibili.com" in lowered or "b23.tv" in lowered:
        match = _BV_RE.search(raw)
        return ResourceSource.BILIBILI, match.group(1) if match else None

    # 兜底：纯 BV 号也能导入
    match = _BV_RE.fullmatch(raw)
    if match:
        return ResourceSource.BILIBILI, match.group(1)

    raise ValueError("暂不支持该链接，目前仅支持 YouTube 与哔哩哔哩")


# 双语对照期望的译文语言，按优先级尝试。
# YouTube 的自动翻译轨道语言代码形如 zh-Hans / zh-Hant，也有 zh-CN 这类写法。
CHINESE_SUBTITLE_LANGS = ("zh-Hans", "zh-CN", "zh-Hant", "zh-TW", "zh")


def _is_chinese_lang(lang: str) -> bool:
    """判断是否是中文轨道：原文已是中文时无需再找译文"""
    return (lang or "").lower().startswith("zh")


def build_embed_url(platform: str, platform_id: str) -> str:
    """
    拼装 iframe 播放地址

    YouTube 走 IFrame Player API 可用域名（www.youtube-nocookie.com 减少追踪）；
    B站走官方 player 页面。
    """
    if platform == ResourceSource.YOUTUBE:
        # enablejsapi=1 用于父页 postMessage 双向通信
        return (
            f"https://www.youtube-nocookie.com/embed/{platform_id}"
            "?enablejsapi=1&playsinline=1&rel=0&modestbranding=1"
        )
    if platform == ResourceSource.BILIBILI:
        return f"https://player.bilibili.com/player.html?bvid={platform_id}&autoplay=0&high_quality=1"
    return ""


def _pick_subtitle_langs(info: Dict[str, Any], preferred: List[str]) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    挑出实际可用的字幕语言轨道

    yt-dlp 返回的结构中，`subtitles` 是人工上传字幕，`automatic_captions` 是自动字幕，
    两者 key 均为语言代码（如 "zh-Hans"、"en-orig"）。

    Returns:
        (最终使用的语言列表, {"manual": [...], "auto": [...]})
    """
    manual = list((info or {}).get("subtitles") or {})
    auto = list((info or {}).get("automatic_captions") or {})
    # 视频原始语言（如 "en"）。其自动字幕属于「原文 ASR」，
    # 不受 YouTube 对翻译类自动字幕的 HTTP 429 限流影响，可用性远高于翻译轨道。
    original = str((info or {}).get("language") or "")

    selected: List[str] = []

    def _try_add(lang: str) -> None:
        if not lang:
            return
        if lang in manual or lang in auto:
            if lang not in selected:
                selected.append(lang)

    # 1) 人工字幕：质量最高，且不受 429 限流
    for lang in preferred:
        if lang in manual:
            _try_add(lang)
    # 2) 原始语言轨道：人工优先，其次原文 ASR（en-orig / en-GB 等同类变体也算）
    _try_add(original)
    for candidate in auto:
        if original and candidate.split("-")[0] == original.split("-")[0]:
            _try_add(candidate)
    # 3) 用户偏好的其余轨道：可能是翻译字幕，存在 429 风险，放最后兜底
    for lang in preferred:
        _try_add(lang)
    # 4) 偏好一个都没命中：退化到任意人工字幕，最后任意自动字幕
    if not selected:
        selected = manual[:1] or auto[:1]

    return selected[:MAX_SUBTITLE_LANGS], {"manual": manual, "auto": auto}


def _index_subtitle_files(directory: str) -> Dict[str, List[str]]:
    """把目录里的字幕文件按语言代码归类（yt-dlp 文件名形如 `<id>.<ext>.<lang>.vtt`）"""
    by_lang: Dict[str, List[str]] = {}
    if not os.path.isdir(directory):
        return by_lang

    for name in os.listdir(directory):
        lower = name.lower()
        if not lower.endswith(_SUBTITLE_EXTS):
            continue
        # 语言标记位于字幕扩展名之前，如 "...zh-Hans.vtt"
        stem = lower.rsplit(".", 1)[0]
        lang_part = stem.rsplit(".", 1)[-1]
        by_lang.setdefault(lang_part, []).append(name)
    return by_lang


def _read_subtitle_files(
    directory: str, langs: List[str], allow_fallback: bool = True
) -> Tuple[List[dict], str]:
    """
    按语言优先级读取落盘的字幕文件

    Args:
        directory: yt-dlp 落盘目录
        langs: 语言优先级列表
        allow_fallback: 指定语言都没命中时，是否回退到任意已落盘的字幕。
            逐个语言尝试下载时应传 False，否则会误读到上一轮遗留的其它语言文件。

    Returns:
        (cues, 实际命中的语言)

    取第一个解析出内容的轨道，而不是只认首选语言：YouTube 常对
    「翻译类自动字幕」返回 429，若只盯首选语言，即便原文轨道已成功落盘也会被丢弃。
    """
    by_lang = _index_subtitle_files(directory)
    if not by_lang:
        return [], ""

    def _read(name: str, lang: str) -> List[dict]:
        try:
            with open(os.path.join(directory, name), "r", encoding="utf-8", errors="ignore") as handle:
                return parse_subtitle(handle.read(), language=lang)
        except Exception as exc:  # noqa: BLE001 - 单个文件损坏不应中断整条导入链路
            logger.error(f"读取字幕文件失败 {name}: {exc}")
            return []

    for lang in langs:
        for name in sorted(by_lang.get(lang.lower(), [])):
            cues = _read(name, lang)
            if cues:
                logger.info(f"字幕命中 lang={lang} file={name} cues={len(cues)}")
                return cues, lang

    if not allow_fallback:
        return [], ""

    # 首选语言全部落空：回退到任意一份成功落盘的字幕，有字幕总比没有强
    for lang, names in by_lang.items():
        for name in sorted(names):
            cues = _read(name, lang)
            if cues:
                logger.warning(f"偏好语言字幕不可用，回退到 lang={lang} file={name}")
                return cues, lang

    return [], ""


def _fetch_blocking(url: str, preferred_langs: List[str]) -> Dict[str, Any]:
    """
    同步抓取（在线程池中执行）

    Raises:
        MediaUnavailableError: yt-dlp 未安装
        Exception: 抓取过程中的上游错误，由调用方统一兜底
    """
    try:
        import yt_dlp  # noqa: PLC0415 - 延迟导入，未安装时不阻断其他功能
    except ImportError as exc:
        raise MediaUnavailableError(
            "未安装 yt-dlp，无法导入视频链接。请执行：pip install -U yt-dlp"
        ) from exc

    platform, platform_id = detect_platform(url)

    with tempfile.TemporaryDirectory(prefix="learning-sub-") as tmpdir:
        options: Dict[str, Any] = {
            "skip_download": True,           # 绝不下载视频本体
            "writesubtitles": True,          # 人工字幕
            # 自动字幕：yt-dlp 新版把该参数改名为 writeautomaticsub，
            # 旧名 writeautomaticsubtitles 已被忽略（且只影响自动字幕，人工字幕照常）。
            # 新旧两个都给，兼容不同版本；yt-dlp 会忽略不认识的那个。
            "writeautomaticsub": True,
            "writeautomaticsubtitles": True,
            "subtitlesformat": "vtt/srt/best",
            "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
            "quiet": True,                   # 不往 stdout 打印，改用下面的 logger 落日志
            "no_warnings": False,            # 保留告警，交给 _YtdlpLogger 记录以便排查
            "noplaylist": True,
            "socket_timeout": 30,
            "extractor_retries": 2,
            "fragment_retries": 2,
            "retries": 2,
            "ignoreerrors": False,
            "logger": _YtdlpLogger(),
        }
        if settings.YTDLP_PROXY:
            options["proxy"] = settings.YTDLP_PROXY
        if settings.YTDLP_COOKIEFILE and os.path.isfile(settings.YTDLP_COOKIEFILE):
            # 部分视频（会员/年龄限制）必须带登录态才能拿到字幕
            options["cookiefile"] = settings.YTDLP_COOKIEFILE
        if settings.YTDLP_PLAYER_CLIENT and platform == ResourceSource.YOUTUBE:
            # 切换播放器客户端可绕过针对默认客户端的 PO Token 校验
            options["extractor_args"] = {
                "youtube": {"player_client": [settings.YTDLP_PLAYER_CLIENT]}
            }

        # JS runtime：YouTube 签名必需，缺失则自动字幕必定抓不到
        runtime = (settings.YTDLP_JS_RUNTIME or "").strip() or _detect_js_runtime()
        if runtime:
            # 支持 `node` 与 `node:绝对路径` 两种写法
            name, _, runtime_path = runtime.partition(":")
            options["js_runtimes"] = {name.strip(): {"path": runtime_path} if runtime_path else {}}
        else:
            logger.warning(
                "未探测到 JS runtime（node/deno/bun），YouTube 自动字幕可能无法下载；"
                "请安装 Node.js 或配置 YTDLP_JS_RUNTIME"
            )

        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)
            if info is None:
                raise MediaUnavailableError("无法解析该链接，请确认视频可公开访问")

            # 播放列表场景取第一个可用条目
            if info.get("_type") == "playlist" and info.get("entries"):
                info = next((e for e in info["entries"] if e), info)

            langs, availability = _pick_subtitle_langs(info, preferred_langs)

            # 先把元数据取出来：后面的字幕下载会就地改写 info_dict
            final_id = platform_id or info.get("id") or ""
            duration = int(info.get("duration") or 0)
            cover = info.get("thumbnail") or ""
            if not cover and platform == ResourceSource.YOUTUBE and final_id:
                cover = f"https://i.ytimg.com/vi/{final_id}/hqdefault.jpg"
            title = (info.get("title") or "").strip() or "未命名视频"
            description = (info.get("description") or "")[:2000]
            source_url = info.get("webpage_url") or url

            # 逐个语言尝试，取第一个真正解析出内容的轨道。
            # 不能一次性把 langs 全交给 yt-dlp：翻译类自动字幕常被限流（HTTP 429），
            # 任一条失败会抛出 DownloadError 中断整条导入，连本可成功的原文轨道也拿不到。
            cues: List[dict] = []
            used_lang = ""
            for lang in langs:
                options["subtitleslangs"] = [lang]
                try:
                    _download_subtitles_only(yt_dlp, options, info, url)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"字幕语言 {lang} 下载失败，尝试下一个：{exc}")
                    continue

                parsed, hit = _read_subtitle_files(tmpdir, [lang], allow_fallback=False)
                if parsed:
                    cues, used_lang = parsed, hit
                    break

            # ---- 副轨道：中文译文，用于双语对照 ----
            # 原文已是中文就不必再抓；抓不到也完全不影响主流程，只是没有双语。
            secondary_cues: List[dict] = []
            secondary_lang = ""
            original_lang = str(info.get("language") or "") or used_lang
            if cues and not _is_chinese_lang(used_lang):
                for lang in CHINESE_SUBTITLE_LANGS:
                    options["subtitleslangs"] = [lang]
                    try:
                        _download_subtitles_only(yt_dlp, options, info, url)
                    except Exception as exc:  # noqa: BLE001 - 翻译轨道常被限流
                        logger.warning(f"中文字幕轨道 {lang} 下载失败，尝试下一个：{exc}")
                        continue

                    # 必须按 lang 精确读取：目录里还留着上一步的原文文件
                    parsed, hit = _read_subtitle_files(tmpdir, [lang], allow_fallback=False)
                    if parsed:
                        secondary_cues, secondary_lang = parsed, hit
                        logger.info(f"中文字幕命中 lang={hit} cues={len(parsed)}")
                        break

            tracks: List[Dict[str, Any]] = []
            if cues:
                tracks.append(
                    {
                        "lang": used_lang,
                        "cues": cues,
                        "source": TranscriptSource.PLATFORM,
                        "is_original": True,
                    }
                )
            if secondary_cues:
                tracks.append(
                    {
                        "lang": secondary_lang,
                        "cues": secondary_cues,
                        "source": TranscriptSource.PLATFORM,
                        "is_original": False,
                    }
                )

            return {
                "platform": platform,
                "platform_id": final_id,
                "title": title,
                "description": description,
                "duration_seconds": duration,
                "cover_url": cover,
                "source_url": source_url,
                "availability": availability,
                # 实际写入库的语言（可能不是首选语言，见 _read_subtitle_files 的回退逻辑）
                "target_lang": used_lang,
                "original_lang": original_lang,
                "requested_langs": langs,
                "cues": cues,
                # 全部可用轨道（原文 + 中文译文），供双语落库
                "tracks": tracks,
            }


def _download_subtitles_only(
    yt_dlp: Any, options: Dict[str, Any], info: Dict[str, Any], url: str
) -> None:
    """
    只下载字幕文件（视频本体始终跳过）

    优先复用已解析好的 info_dict 走 process_ie_result，避免为了拿字幕再走一遍
    extract：每多一次网络往返，就多一次被限流（429）或超时的机会。
    process_ie_result 属于半公开 API，若不可用则回退到重新 download([url])。
    """
    with yt_dlp.YoutubeDL(options) as sub_downloader:
        try:
            # 传副本：yt-dlp 会就地修改传入的 info_dict
            sub_downloader.process_ie_result(copy.deepcopy(info), download=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"复用解析结果下载字幕失败，回退到重新解析：{exc}")
            sub_downloader.download([url])


_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="learning-media")


class MediaService:
    """媒体抓取服务"""

    def __init__(self) -> None:
        self.timeout = settings.LEARNING_MEDIA_TIMEOUT

    @staticmethod
    def is_ytdlp_installed() -> bool:
        """检查 yt-dlp 是否可用（供前端在导入前给出友好提示）"""
        try:
            import yt_dlp  # noqa: PLC0415, F401

            return True
        except ImportError:
            return False

    async def fetch(self, url: str, preferred_langs: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        异步抓取：把阻塞的 yt-dlp 调用丢进线程池并加超时

        Raises:
            MediaUnavailableError: 依赖缺失或超时
            ValueError: 链接平台不支持
        """
        langs = preferred_langs or ["zh-Hans", "zh-CN", "zh", "zh-TW", "en"]
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(_executor, _fetch_blocking, url, langs),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError as exc:
            logger.error(f"抓取视频信息超时: {settings.LEARNING_MEDIA_TIMEOUT}s")
            raise MediaUnavailableError("抓取超时，请稍后重试或检查网络代理配置") from exc


def get_media_service() -> MediaService:
    """媒体服务工厂（无状态，不依赖 DB Session）"""
    return MediaService()
