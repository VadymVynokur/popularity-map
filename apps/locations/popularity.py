from decimal import Decimal

RATING_WEIGHT = 0.50
REVIEWS_WEIGHT = 0.30
VIEWS_WEIGHT = 0.20
REVIEWS_SATURATION = 10.0
VIEWS_SATURATION = 50.0
RATING_MAX = 5.0
SCORE_SCALE = 100.0


def calculate_popularity(
    *,
    rating: Decimal | float | None,
    review_count: int,
    views_7d: int,
) -> float:
    rating_value = float(rating) if rating is not None else 0.0
    reviews = float(review_count)
    views = float(views_7d)
    rating_component = rating_value / RATING_MAX
    reviews_component = reviews / (reviews + REVIEWS_SATURATION)
    views_component = views / (views + VIEWS_SATURATION)
    score = SCORE_SCALE * (
        RATING_WEIGHT * rating_component
        + REVIEWS_WEIGHT * reviews_component
        + VIEWS_WEIGHT * views_component
    )
    return round(score, 2)
