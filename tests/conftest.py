# Load LightGBM's OpenMP runtime before any test imports torch: the other order crashes on macOS.
# (test_seqmodel also runs torch single-threaded, so the two runtimes never both run thread pools.)
try:
    import lightgbm  # noqa: F401
except ImportError:
    pass
