class AssetStoreError(Exception):
    pass


class MappingError(AssetStoreError):
    pass


class PersistenceError(AssetStoreError):
    pass


__all__ = ["AssetStoreError", "MappingError", "PersistenceError"]
