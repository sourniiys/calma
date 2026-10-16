import os


# Static test-only key. Never use this key outside automated tests.
os.environ.setdefault(
	"CALMA_DATA_ENCRYPTION_KEY",
	"MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
)
os.environ.setdefault("CALMA_DB_PATH", ":memory:")