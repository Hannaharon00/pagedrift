from loguru import logger

# Processor capabilities
supports_visual_selector = True
supports_browser_steps = True
supports_text_filters_and_triggers = True
supports_text_filters_and_triggers_elements = True
supports_request_type = True



def _task(watch, update_handler):
    from changedetectionio.content_fetchers.exceptions import ReplyWithContentButNoText
    from changedetectionio.processors.text_json_diff.processor import FilterNotFoundInResponse

    text_after_filter = ''

    try:
        # The slow process (we run 2 of these in parallel)
        # Always force reprocess for preview - we want to show the filtered content regardless of checksums
        changed_detected, update_obj, text_after_filter = update_handler.run_changedetection(watch=watch, force_reprocess=True)
    except FilterNotFoundInResponse as e:
        text_after_filter = f"Filter not found in HTML: {str(e)}"
    except ReplyWithContentButNoText as e:
        text_after_filter = "Filter found but no text (empty result)"
    except Exception as e:
        text_after_filter = f"Error: {str(e)}"

    if not text_after_filter.strip():
        text_after_filter = 'Empty content'

    # because run_changedetection always returns bytes due to saving the snapshots etc
    text_after_filter = text_after_filter.decode('utf-8') if isinstance(text_after_filter, bytes) else text_after_filter

    return text_after_filter


def _compute_ignore_line_numbers_for_preview(text_pre_extract, ignore_patterns, extract_patterns):
    """1-indexed output line numbers in the post-extract display that correspond
    to input lines matching ignore_text patterns.

    Needed because extract_text (#4138) transforms line content — e.g. "0.54.10"
    becomes ".54.10" — so a substring match for "0.54.10" against the post-extract
    text fails and the preview UI can no longer mark the line as ignored. We find
    the ignored line numbers in the pre-extract text and replay extract_by_regex
    line-by-line to map them forward.
    """
    from changedetectionio import html_tools
    from changedetectionio.processors.text_json_diff.processor import ContentTransformer

    if not text_pre_extract or not ignore_patterns:
        return []

    ignored_input_lines = set(
        html_tools.strip_ignore_text(
            content=text_pre_extract,
            wordlist=ignore_patterns,
            mode='line numbers'
        )
    )
    if not ignored_input_lines:
        return []

    if not extract_patterns:
        return sorted(ignored_input_lines)

    # Replay extract_by_regex per-line. Each emitted match ends with exactly one
    # '\n', so counting newlines tells us how many output lines this input produced.
    output_line_counter = 0
    result = []
    for input_idx, line in enumerate(text_pre_extract.splitlines()):
        is_ignored = (input_idx + 1) in ignored_input_lines
        matches_in_line = ContentTransformer.extract_by_regex(line, extract_patterns).count('\n')
        for _ in range(matches_in_line):
            output_line_counter += 1
            if is_ignored:
                result.append(output_line_counter)

    return result


