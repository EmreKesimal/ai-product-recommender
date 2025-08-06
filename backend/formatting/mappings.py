"""
Static mappings used throughout the product recommendation system.

- FEATURE_MAPPINGS:
    Free-text feature keywords -> MongoDB field *names* (string).
    Bunlar genelde "Var/Yok" veya $text aramalarına destek için kullanılır.

- FEATURE_EQUALS_MAPPINGS:
    Free-text anahtar -> (MongoDB field, exact value) eşlemesi.
    Burada alan için doğrudan eşitlik (==) veya negatif durumda eşit değil (!=) filtresi uygulanır.

- CATEGORY_PREFERENCES (legacy) ve NEGATIVE_CATEGORY_ROUTING (yeni):
    Negatif istek geldiğinde kategoriyi daha uygun bir alt kategoriye yönlendirmeye yarar.

Bu dosya tek bir yerden bakımı kolaylaştırır; diğer modüller bu sabitleri içe aktarır.
"""

# -----------------------------
# Basit anahtar -> alan adı (string) eşleşmeleri
# (Legacy akışlarda "Var/Yok" mantığı için kullanılır)
# -----------------------------
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

# -----------------------------
# Eşitlik tabanlı eşleşmeler (alan, değer)
# smart_query.build_smart_query bu sözlükle:
#   - pozitif metin:  field == value
#   - negatif metin:  field != value
# filtreleri oluşturabilir.
# -----------------------------
FEATURE_EQUALS_MAPPINGS = {
    # Kulaklık tipi
    "kulak içi": ("features.Kulaklık Tipi", "Kulak İçi"),
    "kulak ici": ("features.Kulaklık Tipi", "Kulak İçi"),   # yazım varyasyonu
    "kulakiçi": ("features.Kulaklık Tipi", "Kulak İçi"),    # bitişik yazım
    "kulak üstü": ("features.Kulaklık Tipi", "Kulak Üstü"),
    "kulak ustu": ("features.Kulaklık Tipi", "Kulak Üstü"),
    "over ear": ("features.Kulaklık Tipi", "Kulak Üstü"),
    "on ear": ("features.Kulaklık Tipi", "Kulak Üstü"),

    # Buzdolabı/dondurucu özellikleri
    "no frost": ("features.Dondurucu Özelliği", "No Frost"),
    "nofrost": ("features.Dondurucu Özelliği", "No Frost"),
    "less frost": ("features.Dondurucu Özelliği", "Less Frost"),
    "statik": ("features.Dondurucu Özelliği", "Statik"),

    # Buzdolabı tip
    "çift kapılı": ("features.Tip", "Çift Kapılı"),
    "tek kapılı": ("features.Tip", "Tek Kapılı"),
}

# -----------------------------
# Negatif isteklerde kategori yönlendirme (yeni)
# Anahtarlar lower-case karşılaştırma için tasarlandı.
# Değerler DB’de kayıtlı *tam kategori adları* olmalı.
# -----------------------------
NEGATIVE_CATEGORY_ROUTING = {
    # Kulaklık: "kulak içi olmasın" → "Kulak üstü Bluetooth kulaklık"
    ("bluetooth kulaklık", "kulak içi"): "Kulak üstü Bluetooth kulaklık",
    ("kulaklık", "kulak içi"): "Kulak üstü Bluetooth kulaklık",

    # Tersi: "kulak üstü olmasın" → "Kulak İçi Bluetooth Kulaklık"
    ("bluetooth kulaklık", "kulak üstü"): "Kulak İçi Bluetooth Kulaklık",
    ("kulaklık", "kulak üstü"): "Kulak İçi Bluetooth Kulaklık",

    # Süpürge: "dikey olmasın" → "Torbasız Süpürge"
    ("süpürge", "dikey"): "Torbasız Süpürge",
    ("süpürge", "dik"): "Torbasız Süpürge",
}

# -----------------------------
# Legacy kategori tercihleri (mevcut kalsın)
# (Yeni yönlendirme için NEGATIVE_CATEGORY_ROUTING kullanılıyor.)
# -----------------------------
CATEGORY_PREFERENCES = {
    ("süpürge", "dikey"): "Torbasız Süpürge",
    ("süpürge", "dik"): "Torbasız Süpürge",
    ("kulaklık", "kulaküstü"): "Kulak İçi Bluetooth Kulaklık",
    ("kulaklık", "büyük"): "Kulak İçi Bluetooth Kulaklık",
    ("telefon", "android"): "iPhone IOS Cep Telefonları",
    ("telefon", "iphone"): "Android Cep Telefonu",
}

__all__ = [
    "FEATURE_MAPPINGS",
    "FEATURE_EQUALS_MAPPINGS",
    "NEGATIVE_CATEGORY_ROUTING",
    "CATEGORY_PREFERENCES",
]