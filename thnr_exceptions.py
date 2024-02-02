class CouldNotGetChromeDriver(Exception):
    pass


class CouldNotGetObjectFromS3Error(Exception):
    def __init__(self, message="failed to retrieve object from s3"):
        self.message = message
        super().__init__(self.message)


class FailedAfterRetrying(Exception):
    pass


class ServerReturnedEmptyDocumentError(Exception):
    def __init__(self, message="server returned an empty document"):
        self.message = message
        super().__init__(self.message)


class UnsupportedStoryType(Exception):
    def __init__(self, unsupported_story_type=""):
        self.message = f"story type '{unsupported_story_type}' is unsupported"
        super().__init__(self.message)
