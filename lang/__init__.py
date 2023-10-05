"""Top-level package for FIKL."""
# lang/__init__.py

__app_name__ = "fikl"
__version__ = "0.1.0"

(
    SUCCESS,
    QL_ERROR
) = range(2)

ERRORS = {
    QL_ERROR: "query error"
}
