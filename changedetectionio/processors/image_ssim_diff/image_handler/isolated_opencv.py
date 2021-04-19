"""
OpenCV-based subprocess isolation for image comparison.

OpenCV is much more stable in multiprocessing contexts than LibVIPS.
No threading issues, no fork problems, picklable functions.
"""

