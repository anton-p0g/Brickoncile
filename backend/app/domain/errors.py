class PartsCatalogNotFoundError(Exception):
    """Raised when the external catalog has no record of the requested set/minifig."""


class PartsCatalogUnavailableError(Exception):
    """Raised when the external catalog call fails for any other reason."""


class EntityNotFoundError(Exception):
    """Raised when a use case operates on a set/minifig/instance/part that isn't cached locally."""


class EntityOwnedBySetError(Exception):
    """Raised when something owned through a set is deleted on its own. The set's roster would put
    it straight back on the next resync, so the set is where it has to be removed."""


class UnresolvableMinifigReferenceError(Exception):
    """Raised when pasted text cannot be turned into a Rebrickable fig id — either nothing in it
    looks like one, or it identifies the figure in a catalog Rebrickable publishes no mapping
    from. The message says which, since the two need different things from the owner."""


class ImageRecognitionUnavailableError(Exception):
    """Raised when the image-recognition service cannot be reached or refuses the request."""


class UnreadableImageError(Exception):
    """Raised when an uploaded photo is empty, oversized, or not an image the recogniser accepts."""


class CollectionNotFoundError(Exception):
    """Raised when a request names a collection that is not registered."""


class InvalidCollectionNameError(Exception):
    """Raised when a collection display name is empty, unsafe to render, or too long."""


class CollectionNameConflictError(Exception):
    """Raised when a collection display name is already in use, ignoring case."""


class LastCollectionDeletionError(Exception):
    """Raised when deleting a collection would leave the app with no collection to select."""
