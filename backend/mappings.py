"""
Static mappings used throughout the product recommendation system.

``FEATURE_MAPPINGS`` defines a correspondence between user-facing
keywords and the internal MongoDB field names and values. It is used
in ``smart_query.build_smart_query`` to translate natural language
feature requests into database filters.

``CATEGORY_PREFERENCES`` encodes preferences for alternative
categories when the user specifies a negative requirement for a given
category. For example, requesting a "süpürge" but explicitly
excluding "dikey" will redirect the search to ``Torbasız Süpürge``.

These mappings are separated into their own module so they can be
maintained and extended independently without polluting other parts of
the codebase.
"""

# Mapping of Turkish feature keywords to MongoDB field names. The values
# correspond to the keys within the ``features`` subdocument stored in
# MongoDB. For example, a request mentioning "gürültü engelleme"
# triggers a filter on ``features.Aktif Gürültü Önleme (ANC)``.
FEATURE_MAPPINGS = {
    "gürültü engelleme": "features.Aktif Gürültü Önleme (ANC)",
    "anc": "features.Aktif Gürültü Önleme (ANC)",
    "aktif gürültü önleme": "features.Aktif Gürültü Önleme (ANC)",
    "kablosuz": "features.Bağlantı Türü",
    "bluetooth": "features.Bağlantı Türü",
    "pilli": "features.Güç Kaynağı",
    "şarjlı": "features.Güç Kaynağı",
    "su geçirmez": "features.Su Geçirmezlik",
    "toz geçirmez": "features.Toz Geçirmezlik",
}

# Category redirection preferences. When the user expresses a negative
# preference (e.g. "kulaklık" but "kulaküstü" should not exist) the
# query will target the preferred category instead of the originally
# specified one.
CATEGORY_PREFERENCES = {
    ("süpürge", "dikey"): "Torbasız Süpürge",
    ("süpürge", "dik"): "Torbasız Süpürge",
    ("kulaklık", "kulaküstü"): "Kulak İçi Bluetooth Kulaklık",
    ("kulaklık", "büyük"): "Kulak İçi Bluetooth Kulaklık",
    ("telefon", "android"): "iPhone IOS Cep Telefonları",
    ("telefon", "iphone"): "Android Cep Telefonu",
}

__all__ = ["FEATURE_MAPPINGS", "CATEGORY_PREFERENCES"]