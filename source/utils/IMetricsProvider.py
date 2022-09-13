class IMetricsProvider:
    """Interface for providing the current metrics
    """
    def getCurrentMetrics(self) -> list:
        """Get the current metrics

        Returns:
            list: The current metrics
        """
        pass
