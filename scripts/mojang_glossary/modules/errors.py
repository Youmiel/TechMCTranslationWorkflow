class FileError(Exception):
    pass

class FileLoadError(FileError):
    pass

class FileParseError(FileError):
    pass

class VersionNotFoundError(Exception):
    pass

class IntegrityError(Exception):
    pass