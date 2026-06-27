"""Utilities for parsing CSV data."""

from pathlib import Path
from typing import override

import pandas as pd

from src.config import DATA_DIR


class DataParser:
    """Parser for CSV data files."""

    @staticmethod
    def parse_products() -> pd.DataFrame:
        """Parse products CSV file.

        Returns:
            DataFrame with product data (price as float, tags as list)
        """
        df: pd.DataFrame = pd.read_csv(DATA_DIR / "products.csv")
        df["price"] = df["price"].astype(float)
        df["tags"] = df["tags"].apply(lambda x: x.split(","))
        return df

    @staticmethod
    def parse_users() -> pd.DataFrame:
        """Parse users CSV file.

        Returns:
            DataFrame with user data (interests as list, join_date as datetime)
        """
        df: pd.DataFrame = pd.read_csv(DATA_DIR / "users.csv")
        df["interests"] = df["interests"].apply(lambda x: x.split(","))
        df["join_date"] = pd.to_datetime(df["join_date"])
        return df

    @staticmethod
    def parse_categories() -> pd.DataFrame:
        """Parse categories CSV file.

        Returns:
            DataFrame with category data
        """
        return pd.read_csv(DATA_DIR / "categories.csv")

    @staticmethod
    def parse_sellers() -> pd.DataFrame:
        """Parse sellers CSV file.

        Returns:
            DataFrame with seller data (rating as float, joined as datetime)
        """
        df: pd.DataFrame = pd.read_csv(DATA_DIR / "sellers.csv")
        df["rating"] = df["rating"].astype(float)
        df["joined"] = pd.to_datetime(df["joined"])
        return df


class CachedDataParser(DataParser):
    """Data parser with in-memory caching capability."""

    def __init__(self) -> None:
        """Initialize cached parser with empty cache."""
        self._cache: dict[str, pd.DataFrame] = {}

    @override
    def parse_products(self) -> pd.DataFrame:
        """Parse products with caching.

        Returns:
            Cached or freshly parsed product DataFrame
        """
        if "products" not in self._cache:
            self._cache["products"] = super().parse_products()
        return self._cache["products"]

    def get_data(self, data_type: str) -> pd.DataFrame:
        """Get data by type using pattern matching.

        Args:
            data_type: Type of data ('products', 'users', 'categories', 'sellers')

        Returns:
            Parsed DataFrame for the requested type

        Raises:
            ValueError: If data_type is not recognized
        """
        match data_type:
            case "products":
                return self.parse_products()
            case "users":
                return self.parse_users()
            case "categories":
                return self.parse_categories()
            case "sellers":
                return self.parse_sellers()
            case _:
                raise ValueError(f"Unknown data type: {data_type}")
