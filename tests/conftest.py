from pytest import fixture


@fixture
def output_dir(tmp_path):
    """Fixture for writing results to. Can be changed to non temporary directory to review all results."""
    return tmp_path
