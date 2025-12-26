from test.test_points import load_points_sorted, DATA_DIR
from pathlib import Path
import json


def load_aggregated_points_sorted():
    aggregated_points_dir = DATA_DIR / "aggregated_points"
    aggregated_points = sorted(
        aggregated_points_dir.glob("*.json"), key=lambda f: int(f.stem)
    )
    return [json.loads(f.read_text()) for f in aggregated_points]


class TestAggregatePoints:
    def test_aggregate_points_borders_match_points_borders(self):
        aggregated_points = load_aggregated_points_sorted()
        points = load_points_sorted()
        for i in range(len(aggregated_points)):
            for user, data in aggregated_points[i]["points"].items():
                assert (
                    sum(
                        [
                            point["points"].get(user.lower(), 0)
                            for point in points[: i + 1]
                        ]
                    )
                    == data["cumulative_points"]
                )

            assert (
                sum([sum(point["points"].values()) for point in points[: i + 1]])
                == aggregated_points[i]["metadata"]["total_points_all_users"]
            )
            assert (
                sum(user_points for _, user_points in points[i]["points"].items())
                == aggregated_points[i]["metadata"]["day_points"]
            )
