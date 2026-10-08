"""Shared, Spark-free logic for the Banksia Mobile NOC Lakeflow pipeline.

The pipeline code under `pipelines/netmon/` imports these modules for its schemas, data-quality rules,
detection thresholds, topology hierarchy and scoring definitions. Rules are kept as plain data and
rendered to Spark SQL here, so the same definitions can be unit-tested locally without Spark.
"""

__version__ = "0.1.0"
