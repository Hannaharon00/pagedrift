from loguru import logger

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


