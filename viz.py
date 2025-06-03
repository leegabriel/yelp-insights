"""
Visualize Yelp statistics. 
"""

import polars as pl
import plotly.express as px
import requests

biz_df = pl.read_ndjson("data/yelp_academic_dataset_business.json")
"""
Columns:
['business_id', 'name', 'address', 'city', 'state', 'postal_code', 'latitude', 'longitude', 'stars', 'review_count', 'is_open', 'attributes', 'categories', 'hours']
"""
rev_df = pl.read_ndjson("data/yelp_academic_dataset_review.json")
"""
Columns:
['review_id', 'user_id', 'business_id', 'stars', 'useful', 'funny', 'cool', 'text', 'date']
"""

STATE = "CA"

# To promote fairness, let's concentrate on actual business categories like "restaurant".
# Use U.S. Census data to remove ethnicity, which are *food* types, not *business* types.
# Thanks to Chad Gosselin for curating this list (https://github.com/cgio/global-ethnicities).
ethnicity_url = "https://raw.githubusercontent.com/cgio/global-ethnicities/master/output/ethnicities.json"
ethnicity_response = requests.get(ethnicity_url)
ethnicities_json = ethnicity_response.json()
ethnicity_terms = set([entry for entry in ethnicities_json])

state_biz_ids = biz_df.filter(pl.col("state") == STATE).select("business_id", "categories")
#print(state_biz_ids[:10])

# Get reviews containing the biz_ids
state_reviews = rev_df.join(state_biz_ids, on="business_id", how="inner")
state_reviews = state_reviews.filter(pl.col("categories").is_not_null())

# Split categories, and explode the categories
state_reviews = state_reviews.with_columns(
        pl.col("categories")
        .str.split(",")
        ).explode("categories")

# Split and explode categories
state_reviews = state_reviews.with_columns(
    pl.col("categories").str.split(",")
).explode("categories")

# Strip whitespace from exploded categories
state_reviews = state_reviews.with_columns(
    pl.col("categories").str.strip_chars()
)

# Filter out ethnic categories using the external list
# This is to promote fairness and remove bias.
state_reviews = state_reviews.filter(
    ~pl.col("categories").is_in(list(ethnicity_terms))
)

# Compute global average across all state reviews
global_avg = state_reviews.select(pl.col("stars").mean()).item()
print(f"The global review average for the state of {STATE} is {global_avg}")

# Do bayesian average (smoothing)
C = 100 # smoothing constant
category_bayes = (
    state_reviews.group_by("categories")
    .agg(
        pl.col("stars").mean().alias("avg_stars"),
        pl.len().alias("num_reviews")
    )
    .with_columns(
        (
            (C * global_avg + pl.col("num_reviews") * pl.col("avg_stars")) 
            / (C + pl.col("num_reviews"))
        ).alias("bayesian_avg")
    )
    .sort("bayesian_avg", descending=True)
)

print(category_bayes)

# --- All categories ---
fig = px.bar(
    category_bayes.to_arrow(),
    x="bayesian_avg",
    y="categories",
    orientation="h",
    title=f"Categories in {STATE} Ranked by Average Stars",
    labels={"bayesian_avg": "Average Stars", "categories": "Category"}
)
fig.update_layout(
    yaxis=dict(
        categoryorder="array",
        categoryarray=category_bayes.sort("bayesian_avg")["categories"].to_list()
    )
)
fig.show()

# --- Top 50 ---
top_50 = category_bayes.sort("bayesian_avg", descending=True).head(50)
top_50_arrow = top_50.to_arrow()
top_50_categories = top_50.sort("bayesian_avg")["categories"].to_list()

fig_top50 = px.bar(
    top_50_arrow,
    x="bayesian_avg",
    y="categories",
    orientation="h",
    title=f"Top 50 Categories in {STATE} by Average Stars",
    labels={"bayesian_avg": "Average Stars (C=100 smoothing)", "categories": "Category"},
    height=1000
)
fig_top50.update_layout(
    yaxis=dict(
        categoryorder="array",
        categoryarray=top_50_categories
    ),
    yaxis_title="",
    xaxis_title="Bayesian Avg Stars"
)
fig_top50.show()

# --- Bottom 50 ---
bottom_50 = category_bayes.sort("bayesian_avg", descending=False).head(50)
bottom_50_arrow = bottom_50.to_arrow()
bottom_50_categories = bottom_50.sort("bayesian_avg")["categories"].to_list()

fig_bottom50 = px.bar(
    bottom_50_arrow,
    x="bayesian_avg",
    y="categories",
    orientation="h",
    title=f"Bottom 50 Categories in {STATE} by Average Stars",
    labels={"bayesian_avg": "Average Stars (C=100 smoothing)", "categories": "Category"},
    height=1000
)
fig_bottom50.update_layout(
    yaxis=dict(
        categoryorder="array",
        categoryarray=bottom_50_categories
    ),
    yaxis_title="",
    xaxis_title="Average Stars (C=100 smoothing)"
)
fig_bottom50.show()

