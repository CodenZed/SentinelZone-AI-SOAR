class ServiceError(Exception):
    def __init__(self, code: str, status: int = 409):
        self.code, self.status = code, status
        super().__init__(code)


class DependencyUnavailable(ServiceError):
    def __init__(self, code="dependency_unavailable"):
        super().__init__(code, 503)
