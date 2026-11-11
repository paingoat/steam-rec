"""Raw (Bronze) schemas, verified against Kaggle v28 headers on 2026-11-11."""

from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    FloatType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)

GAMES = StructType([
    StructField("app_id", IntegerType()), StructField("title", StringType()),
    StructField("date_release", StringType()), StructField("win", BooleanType()),
    StructField("mac", BooleanType()), StructField("linux", BooleanType()),
    StructField("rating", StringType()), StructField("positive_ratio", IntegerType()),
    StructField("user_reviews", LongType()), StructField("price_final", DoubleType()),
    StructField("price_original", DoubleType()), StructField("discount", DoubleType()),
    StructField("steam_deck", BooleanType()),
])

USERS = StructType([
    StructField("user_id", LongType()), StructField("products", IntegerType()), StructField("reviews", IntegerType()),
])

RECOMMENDATIONS = StructType([
    StructField("app_id", IntegerType()), StructField("helpful", IntegerType()), StructField("funny", IntegerType()),
    StructField("date", StringType()), StructField("is_recommended", BooleanType()), StructField("hours", FloatType()),
    StructField("user_id", LongType()), StructField("review_id", LongType()),
])

GAMES_METADATA_COLUMNS = ["app_id", "description", "tags"]
RAW_HEADERS = {
    "games.csv": [f.name for f in GAMES.fields],
    "users.csv": [f.name for f in USERS.fields],
    "recommendations.csv": [f.name for f in RECOMMENDATIONS.fields],
}
