"""
Visualize Yelp statistics.
"""

import polars as pl
import plotly.express as px
import requests

biz_df = pl.read_ndjson("data/yelp_academic_dataset_business.json")
rev_df = pl.read_ndjson("data/yelp_academic_dataset_review.json")

STATE = "CA"

# Load ethnicity list
ethnicity_url = "https://raw.githubusercontent.com/cgio/global-ethnicities/master/output/ethnicities.json"
ethnicity_response = requests.get(ethnicity_url)
ethnicity_terms = set(ethnicity_response.json())

# Filter businesses in target state
state_biz_ids = biz_df.filter(pl.col("state") == STATE).select("business_id", "categories")

# Join and filter reviews for those businesses
state_reviews = rev_df.join(state_biz_ids, on="business_id", how="inner")
state_reviews = state_reviews.filter(pl.col("categories").is_not_null())

# Process categories
state_reviews = (
    state_reviews
    .with_columns(pl.col("categories").str.split(","))
    .explode("categories")
    .with_columns(pl.col("categories").str.strip_chars())
    .filter(~pl.col("categories").is_in(list(ethnicity_terms)))
)

# Compute global average
global_avg = state_reviews.select(pl.col("stars").mean()).item()
print(f"The global review average for the state of {STATE} is {global_avg:.2f}")

# Compute raw category statistics and drop small categories
category_stats = (
    state_reviews.group_by("categories")
    .agg(
        pl.col("stars").mean().alias("avg_stars"),
        pl.len().alias("num_reviews")
    )
    .filter(pl.col("num_reviews") >= 100)
    .sort("avg_stars", descending=True)
)

print(category_stats)

# --- All categories ---
fig = px.bar(
    category_stats.to_arrow(),
    x="avg_stars",
    y="categories",
    orientation="h",
    title=f"Categories in {STATE} with ≥100 Reviews Ranked by Average Stars",
    labels={"avg_stars": "Average Stars", "categories": "Category"}
)
fig.update_layout(
    yaxis=dict(
        categoryorder="array",
        categoryarray=category_stats.sort("avg_stars")["categories"].to_list()
    )
)
fig.show()

# --- Top 50 ---
top_50 = category_stats.head(50)
fig_top50 = px.bar(
    top_50.to_arrow(),
    x="avg_stars",
    y="categories",
    orientation="h",
    title=f"Top 50 Categories in {STATE} (≥100 Reviews)",
    labels={"avg_stars": "Average Stars", "categories": "Category"},
    height=1000
)
fig_top50.update_layout(
    yaxis=dict(
        categoryorder="array",
        categoryarray=top_50.sort("avg_stars")["categories"].to_list()
    )
)
fig_top50.show()

# --- Bottom 50 ---
bottom_50 = category_stats.sort("avg_stars").head(50)
fig_bottom50 = px.bar(
    bottom_50.to_arrow(),
    x="avg_stars",
    y="categories",
    orientation="h",
    title=f"Bottom 50 Categories in {STATE} (≥100 Reviews)",
    labels={"avg_stars": "Average Stars", "categories": "Category"},
    height=1000
)
fig_bottom50.update_layout(
    yaxis=dict(
        categoryorder="array",
        categoryarray=bottom_50.sort("avg_stars")["categories"].to_list()
    )
)
fig_bottom50.show()
