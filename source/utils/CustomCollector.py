from .MetricsProvider import MetricsProvider

class CustomCollector(object):
    """A custom Collector to report Metrics.
       See https://github.com/prometheus/client_python#custom-collectors

    Args:
        object (_type_): _description_
    """

    def __init__(self, metrics_provider:MetricsProvider):
        self.metrics_provider = metrics_provider

    def collect(self):
        return self.metrics_provider.current_metrics
