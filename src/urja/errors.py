class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def protocol_error() -> ServiceError:
    return ServiceError("upstream_protocol", "The portal returned an unexpected data format.")
