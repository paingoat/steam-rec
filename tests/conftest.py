import pytest


@pytest.fixture(scope="session")
def spark(tmp_path_factory):
    from pyspark.sql import SparkSession

    s = (SparkSession.builder.master("local[2]").appName("tests")
         .config("spark.sql.shuffle.partitions", "4").config("spark.ui.enabled", "false")
         .config("spark.sql.session.timeZone", "UTC").getOrCreate())
    s.sparkContext.setLogLevel("ERROR")
    s.sparkContext.setCheckpointDir(str(tmp_path_factory.mktemp("ckpt")))
    yield s
    s.stop()
