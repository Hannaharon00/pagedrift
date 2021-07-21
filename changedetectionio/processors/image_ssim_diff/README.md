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

# Gaussian blur sigma for OpenCV (0 = no blur, higher = more blur)
OPENCV_BLUR_SIGMA=0.8  # Default

# Minimum change percentage to trigger detection
OPENCV_MIN_CHANGE_PERCENT=0.1  # Default (0.1%)
PIXELMATCH_MIN_CHANGE_PERCENT=0.1  # Default

# Diff visualization image size limits (pixels)
MAX_DIFF_HEIGHT=8000  # Default
MAX_DIFF_WIDTH=900  # Default
```

### Per-Watch Configuration

- **Comparison Threshold**: Can be configured per-watch in the edit form
  - Very low sensitivity (10) - Only major changes
  - Low sensitivity (20) - Significant changes
  - Medium sensitivity (30) - Moderate changes (default)
  - High sensitivity (50) - Small changes
  - Very high sensitivity (75) - Any visible change

### Visual Selector (Region Comparison)

Use the "Include filters" field with CSS selectors or XPath to compare only specific page regions:

```
.content-area
//div[@id='main']
```

The processor will automatically crop both screenshots to the bounding box of the first matched element.

## Dependencies

### Required
- `opencv-python-headless>=4.8.0.76` - Fast image comparison
- `Pillow (PIL)` - Image loading and manipulation
- `numpy` - Array operations

### Optional
- `pybind11-pixelmatch>=0.1.3` - Alternative comparison method with anti-aliasing detection

## Change Detection Interpretation

- **0%** = Identical images (or below minimum change threshold)
- **0.1-1%** = Minor differences (anti-aliasing, slight rendering differences)
- **1-5%** = Noticeable changes (text updates, small content changes)
- **5-20%** = Significant changes (layout shifts, content additions)
- **>20%** = Major differences (page redesign, large content changes)

## Technical Notes

### Memory Management
```python
# Explicit cleanup for long-running processes
img.close()  # Close PIL Images
buffer.close()  # Close BytesIO buffers
del large_array  # Mark numpy arrays for GC
```

### Diff Image Generation
- Format: JPEG (quality=85, optimized)
- Highlight: Red overlay (50% blend with original)
- Auto-downscaling: Large screenshots downscaled for faster rendering
- Base64 embedded: For direct template rendering

### OpenCV Blur Parameters
The Gaussian blur reduces sensitivity to:
- Font rendering differences
- Anti-aliasing variations
- JPEG compression artifacts
- Minor pixel shifts (1-2 pixels)

Increase `OPENCV_BLUR_SIGMA` to make comparison more tolerant of these differences.

