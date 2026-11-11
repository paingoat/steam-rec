from __future__ import annotations

import os

from steam_rec.common.config import Config, s3_settings


def get_spark(cfg: Config, app_name: str = "steam-rec"):
    from pyspark.sql import SparkSession

    sc = cfg.spark
    local_dir = cfg.resolve_path(sc.local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PYSPARK_PYTHON", os.sys.executable)
    b = (
        SparkSession.builder.master(sc.master).appName(app_name)
        .config("spark.driver.memory", sc.driver_memory)
        .config("spark.sql.shuffle.partitions", str(sc.shuffle_partitions))
        .config("spark.local.dir", str(local_dir))
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.parquet.compression.codec", "zstd")
        .config("spark.cleaner.referenceTracking.cleanCheckpoints", "true")
    )
    if cfg.storage.backend == "s3":
        s = s3_settings()
        b = (
            b.config("spark.jars.packages", f"org.apache.hadoop:hadoop-aws:{sc.hadoop_aws_version}")
            .config("spark.hadoop.fs.s3a.endpoint", s["endpoint"])
            .config("spark.hadoop.fs.s3a.access.key", s["access_key"])
            .config("spark.hadoop.fs.s3a.secret.key", s["secret_key"])
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", str(s["endpoint"].startswith("https")).lower())
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
            .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                    "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
        )
    spark = b.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    ckpt = cfg.resolve_path(sc.checkpoint_dir)
    ckpt.mkdir(parents=True, exist_ok=True)
    spark.sparkContext.setCheckpointDir(str(ckpt))
    return spark
