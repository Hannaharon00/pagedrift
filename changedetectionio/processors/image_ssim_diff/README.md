# Fast Screenshot Comparison Processor

Visual/screenshot change detection using ultra-fast image comparison algorithms.

## Overview

This processor uses **OpenCV** by default for screenshot comparison, providing **50-100x faster** performance compared to the previous SSIM implementation while still detecting meaningful visual changes.

## Current Features

- **Ultra-fast OpenCV comparison**: cv2.absdiff with Gaussian blur for noise reduction
- **MD5 pre-check**: Fast identical image detection before expensive comparison
- **Configurable sensitivity**: Threshold-based change detection
- **Three-panel diff view**: Previous | Current | Difference (with red highlights)
- **Direct image support**: Works with browser screenshots AND direct image URLs
- **Visual selector support**: Compare specific page regions using CSS/XPath selectors
- **Download images**: Download any of the three comparison images directly from the diff view

## Performance

- **OpenCV (default)**: 50-100x faster than SSIM
- **Large screenshots**: Automatic downscaling for diff visualization (configurable via `MAX_DIFF_HEIGHT`/`MAX_DIFF_WIDTH`)
- **Memory efficient**: Explicit cleanup of large objects for long-running processes
- **JPEG diff images**: Smaller file sizes, faster rendering

## How It Works

1. **Fetch**: Screenshot captured via browser OR direct image URL fetched
2. **MD5 Check**: Quick hash comparison - if identical, skip comparison
3. **Region Selection** (optional): Crop to specific page region if visual selector is configured
4. **OpenCV Comparison**: Fast pixel-level difference detection with Gaussian blur
5. **Change Detection**: Percentage of changed pixels above threshold = change detected
6. **Visualization**: Generate diff image with red-highlighted changed regions

