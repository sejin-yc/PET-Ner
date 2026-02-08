"""
Pi Gateway 공통 로깅 설정

- LOG_LEVEL 환경변수: DEBUG, INFO, WARNING, ERROR (대소문자 무관, 기본 INFO)
- 잘못된 값(예: VERBOSE)이면 경고 후 INFO로 폴백
- basicConfig force=True 로 중복 설정·핸들러 이중 출력 방지
- stdout 출력 → Docker/K8s에서 수집·검색 가능
"""
import logging
import os

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_VALID_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def configure_logging(default_level: str = "INFO") -> None:
    """전역 로깅 설정. 이미 설정돼 있으면 force=True 로 덮어써서 중복 출력 방지."""
    raw = os.getenv("LOG_LEVEL", default_level)
    raw = default_level if raw is None else str(raw)
    level_name = raw.strip().upper() or default_level.upper()
    invalid = level_name not in _VALID_LEVELS
    if invalid:
        level_name = "INFO"  # VERBOSE, TRACE 등 → 경고 후 INFO

    level = getattr(logging, level_name, logging.INFO)

    # Python 3.8+: force=True 로 기존 핸들러 제거 후 재설정 → 로그 2번 찍힘 방지
    kwargs = dict(level=level, format=_LOG_FORMAT, datefmt=_DATE_FMT)
    try:
        logging.basicConfig(force=True, **kwargs)
    except TypeError:
        logging.basicConfig(**kwargs)

    if invalid:
        logging.getLogger("pi_gateway.log_config").warning(
            "LOG_LEVEL=%r is invalid; using INFO. Valid: %s", raw.strip(), sorted(_VALID_LEVELS)
        )


def get_uvicorn_log_level() -> str:
    """LOG_LEVEL과 동일한 uvicorn 로그 레벨 문자열 (소문자)."""
    raw = os.getenv("LOG_LEVEL", "INFO")
    level_name = str(raw).strip().upper()
    if level_name not in _VALID_LEVELS:
        level_name = "INFO"
    return level_name.lower()


def configure_uvicorn_logging() -> None:
    """uvicorn access/error 로거를 동일 포맷·레벨로 맞춤 (운영에서 한 줄 포맷 통일)."""
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    if level_name not in _VALID_LEVELS:
        level_name = "INFO"
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FMT))

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(name)
        log.setLevel(level)
        log.handlers.clear()
        log.addHandler(handler)
        log.propagate = False
