"""
E-Commerce Pipeline Monitoring — Airflow Plugin

Adds a custom HTML view to the Airflow UI showing recent pipeline run stats.

Usage:
    Copy this plugin into $AIRFLOW_HOME/plugins/.
    Airflow auto-discovers it on restart.
"""

from airflow.plugins_manager import AirflowPlugin
from flask import Blueprint, render_template_string

bp = Blueprint(
    "ecommerce_monitor",
    __name__,
    url_prefix="/ecommerce",
)

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>E-Commerce Pipeline Monitor</title></head>
<body style="font-family:sans-serif;padding:2rem;">
<h1>E-Commerce Analytics Pipeline</h1>
<p>Last 10 DAG runs:</p>
<table border="1" cellpadding="8" style="border-collapse:collapse;">
<tr><th>Run ID</th><th>State</th><th>Start</th><th>End</th><th>Duration</th></tr>
{% for run in runs %}
<tr>
  <td>{{ run.run_id }}</td>
  <td>{{ run.state }}</td>
  <td>{{ run.start_date or '' }}</td>
  <td>{{ run.end_date or '' }}</td>
  <td>{{ run.duration or '' }}</td>
</tr>
{% endfor %}
</table>
<p><a href="/">← Back to Airflow</a></p>
</body>
</html>
"""


@bp.route("/")
def index():
    from airflow.models import DagRun
    from airflow.utils.db import create_session

    with create_session() as session:
        runs = (
            session.query(DagRun)
            .filter(DagRun.dag_id == "ecommerce_analytics_pipeline")
            .order_by(DagRun.execution_date.desc())
            .limit(10)
            .all()
        )
    return render_template_string(INDEX_TEMPLATE, runs=runs)


class EcommerceMonitorPlugin(AirflowPlugin):
    name = "ecommerce_monitor"
    flask_blueprints = [bp]
