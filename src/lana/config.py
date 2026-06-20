"""Configuration for the LANA pipeline."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings. Override any field via env var prefixed LANA_ or a .env file."""

    model_config = SettingsConfigDict(env_prefix="LANA_", env_file=".env", extra="ignore")

    # ABS Data API (SDMX REST) — open, no auth.
    api_base_url: str = "https://data.api.abs.gov.au/rest"
    api_agency_id: str = "ABS"
    api_timeout: int = 120  # Census pulls are large/slow
    api_max_retries: int = 4
    api_throttle_seconds: float = 0.5  # polite serial spacing between calls

    census_year: str = "2021"
    # Time-series tables (C21_T*) carry these years on consistent 2021 boundaries.
    census_period_start: str = "2011"
    census_period_end: str = "2021"

    # Warehouse output: flat files for DB loading.
    file_formats: tuple[str, ...] = ("csv", "parquet")

    # Default proof-of-concept target. The smallest QLD PHN (12 SA2s) → fast end-to-end.
    target_phn: str = "Western Queensland"

    # SA2 batch size for the OR-filtered data key (keeps URLs/responses under API limits).
    sa2_batch_size: int = 50

    # Paths
    data_dir: Path = PROJECT_ROOT / "data"
    reference_dir: Path = PROJECT_ROOT / "data" / "reference"
    bronze_dir: Path = PROJECT_ROOT / "data" / "bronze"
    silver_dir: Path = PROJECT_ROOT / "data" / "silver"
    gold_dir: Path = PROJECT_ROOT / "data" / "gold"
    output_dir: Path = PROJECT_ROOT / "data" / "output"
    warehouse_dir: Path = PROJECT_ROOT / "data" / "warehouse"

    def ensure_dirs(self) -> None:
        for d in (
            self.bronze_dir,
            self.silver_dir,
            self.gold_dir,
            self.output_dir,
            self.warehouse_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
