import functools
import inspect
import logging
import time

import structlog


def _is_structlog_logger(logger) -> bool:
    """Best-effort check to detect structlog loggers."""
    if logger is None:
        return False
    return logger.__class__.__module__.startswith("structlog")


def log_msg(logger, level, msg, extra):
    # If this is a structlog logger, keep structured kwargs
    if _is_structlog_logger(logger):
        if level.lower() == "info":
            logger.info(msg, **extra)
        elif level.lower() == "debug":
            logger.debug(msg, **extra)
        else:
            logger.log(level.upper(), msg, **extra)  # type: ignore[attr-defined]
        return

    # For non-structlog loggers (e.g. Dagster / stdlib logging),
    # stringify the extra dict and log it as part of the message.
    if not isinstance(logger, logging.Logger | logging.LoggerAdapter):
        logger = logging.getLogger()  # root logger

    logging_level = getattr(logging, level.upper(), logging.INFO)
    extra_str = str(extra) if extra is not None else ""
    if extra_str:
        logger.log(logging_level, "%s %s", msg, extra_str)
    else:
        logger.log(logging_level, "%s", msg)


def _build_extra(func_name, args, kwargs, include_inputs):
    extra = {"function_": func_name}
    if include_inputs:
        for k, v in kwargs.items():
            extra["args_" + k] = v

        for i, v in enumerate(args):
            extra["args_" + str(i)] = v
    return extra


def _log_start(ulogger, level, log_start, extra):
    if log_start:
        log_msg(ulogger, level, "start", extra)


def _log_end(ulogger, level, tracker_state: dict) -> None:
    outputs = tracker_state["outputs"]
    value = tracker_state["value"]
    start_time = tracker_state["start_time"]
    extra = tracker_state["extra"]
    end_time = time.time()
    extra["duration_"] = round((end_time - start_time), 3)
    if outputs:
        extra["return_"] = value
    log_msg(ulogger, level, "tracker", extra)


def tracker(
    _func=None, ulogger=None, inputs=False, outputs=False, log_start=False, level="info"
):
    """Log the trace of the program"""
    if ulogger is None:
        ulogger = structlog.get_logger()

    def decorator_tracker(func):
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper_logger(*args, **kwargs):
                extra = _build_extra(func.__name__, args, kwargs, inputs)
                _log_start(ulogger, level, log_start, extra)
                start_time = time.time()
                value = await func(*args, **kwargs)
                _log_end(
                    ulogger,
                    level,
                    {
                        "outputs": outputs,
                        "value": value,
                        "start_time": start_time,
                        "extra": extra,
                    },
                )

                return value

            return wrapper_logger
        else:

            @functools.wraps(func)
            def wrapper_logger(*args, **kwargs):
                extra = _build_extra(func.__name__, args, kwargs, inputs)
                _log_start(ulogger, level, log_start, extra)
                start_time = time.time()
                value = func(*args, **kwargs)
                _log_end(
                    ulogger,
                    level,
                    {
                        "outputs": outputs,
                        "value": value,
                        "start_time": start_time,
                        "extra": extra,
                    },
                )

                return value

            return wrapper_logger

    if _func is None:
        return decorator_tracker
    else:
        return decorator_tracker(_func)
