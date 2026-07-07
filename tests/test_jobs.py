from __future__ import annotations

import unittest

from apple_photos_to_immich.commands import _summarize_jobs


class JobSummaryTests(unittest.TestCase):
    def test_summarize_jobs_aggregates_queue_status_and_counts(self) -> None:
        jobs = {
            "thumbnailGeneration": {
                "queueStatus": {
                    "active": 2,
                    "waiting": 5,
                    "delayed": 1,
                    "paused": 3,
                },
                "jobCounts": {
                    "failed": 4,
                    "completed": 10,
                },
            },
            "metadataExtraction": {
                "queueStatus": {
                    "active": 1,
                    "waiting": 0,
                    "delayed": 2,
                    "paused": 0,
                },
                "jobCounts": {
                    "failed": 1,
                    "completed": 7,
                },
            },
        }

        summary = _summarize_jobs(jobs)

        self.assertEqual(
            summary,
            {
                "active": 3,
                "waiting": 5,
                "delayed": 3,
                "paused": 3,
                "failed": 5,
                "completed": 17,
                "queues": 2,
            },
        )


if __name__ == "__main__":
    unittest.main()
