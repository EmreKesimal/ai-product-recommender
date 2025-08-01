import React from "react";
import styles from "./ProductList.module.css";
import ProductCard from "../ProductCard/ProductCard";

const dummyProducts = [
        {
            imageUrl: "/indir.png",
            title: "Premium Wireless Headphones",
            price: "$299.99",
            rating: 4,
            reviewCount: 1232,
            features: `30 saatlik pil ömrü, aktif gürültü engelleme ve Bluetooth 5.0 ile yüksek ses kalitesi sunar.`,
            description: `AI analizine göre bu kulaklık uzun süreli kullanımda konforu ve izolasyonu ile öne çıkıyor.`,
            reviewSummary: `Kullanıcılar özellikle ses netliği ve rahat yapısından memnun.`
        },
        {
            imageUrl: "/indir.png",
            title: "Smart Watch Series 5",
            price: "$399.99",
            rating: 5,
            reviewCount: 2764,
            features: `Kalp atışı ve uyku takibi, su geçirmez gövde ve 7 günlük pil süresiyle donatılmıştır.`,
            description: `Düzenli egzersiz yapanlar için önerilen, şık ve işlevsel bir akıllı saat.`,
            reviewSummary: `Stil, sağlık verisi doğruluğu ve pil ömrü en çok beğenilen yönleri.`
        },
        {
            imageUrl: "/indir.png",
            title: "Professional Camera Lens",
            price: "$899.99",
            rating: 4,
            reviewCount: 984,
            features: `Portre ve manzara çekimleri için ideal; net odak ve düşük ışıkta yüksek performans.`,
            description: `AI değerlendirmesine göre bu lens keskinlik ve kalite açısından fiyatının hakkını veriyor.`,
            reviewSummary: `Odak kalitesi ve sağlam gövdesi sıkça övülüyor.`
        }
    ]
;

const ProductList: React.FC = () => {
    return (
        <div className={styles.grid}>
            {dummyProducts.map((product, index) => (
                <ProductCard
                    key={index}
                    imageUrl={product.imageUrl}
                    title={product.title}
                    price={product.price}
                    rating={product.rating}
                    reviewCount={product.reviewCount}
                    description={product.description}
                    features={product.features}
                    reviewSummary={product.reviewSummary}
                />
            ))}
        </div>
    );
};

export default ProductList;
