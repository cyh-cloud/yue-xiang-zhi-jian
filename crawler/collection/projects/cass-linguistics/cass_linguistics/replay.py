"""cass-linguistics project fixture replay entry."""

from crawler.collection.shared.crawler_collection.replay import replay_fixture
from .candidate import write_candidate


def replay_cass_fixture(**kwargs):
    return replay_fixture(
        source_id="cass-linguistics",
        candidate_writer=write_candidate,
        **kwargs,
    )
