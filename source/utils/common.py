"""Abstraction for providing metrics from multiple providers.
See See https://github.com/prometheus/client_python#custom-collectors

"""


class IMetricsProvider:
    """Interface for providing the current metrics
    """

    def get_current_metrics(self) -> list:
        """Get the current metrics

        Returns:
            list: The current metrics
        """


class CustomCollector:
    """A custom Collector for reporting Metrics.
    """

    def __init__(self, metrics_provider: IMetricsProvider):
        self.metrics_provider = metrics_provider

    def collect(self) -> list:
        """Collects the current metrics from the IMetricsProvider

        Returns:
            list: the current metrics of the MetricsProvider
        """
        return self.metrics_provider.get_current_metrics()
