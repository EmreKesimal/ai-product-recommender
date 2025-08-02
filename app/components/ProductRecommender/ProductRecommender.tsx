'use client';

import { useState, useEffect } from 'react';
import { HiPaperAirplane } from 'react-icons/hi2';
import axios from 'axios';
import styles from './ProductRecommender.module.css';
import ProductCard from '../ProductCard/ProductCard';

interface Product {
    title: string;
    price: number;
    rating: number;
    review_count: number;
    description: string;
    image: string | null;
    link: string;
}

const ProductRecommender = () => {
    const [query, setQuery] = useState('');
    const [input, setInput] = useState('');
    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(false);

    const handleSend = () => {
        if (input.trim()) {
            setQuery(input.trim());
        }
    };

    useEffect(() => {
        if (!query) return;

        const fetchData = async () => {
            setLoading(true);
            try {
                const res = await axios.post('http://localhost:5001/recommendation', {
                    query
                });
                setProducts(res.data.cards || []);
            } catch (err) {
                console.error('Fetch error:', err);
                setProducts([]);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [query]);

    return (
        <section className={styles.heroSection}>
            <h1 className={styles.heroTitle}>Yapay Zekâ ile Sana Uygun Ürünü Bul!</h1>

            <div className={styles.filterBar}>
                <select className={styles.filterSelect}>
                    <option>Kategori</option>
                    <option>Kulaklık</option>
                    <option>Akıllı Saat</option>
                    <option>Kamera</option>
                </select>

                <select className={styles.filterSelect}>
                    <option>Değerlendirme</option>
                    <option>4+ yıldız</option>
                    <option>3+ yıldız</option>
                </select>

                <select className={styles.filterSelect}>
                    <option>Bütçe Aralığı</option>
                    <option>$0–$100</option>
                    <option>$100–$300</option>
                    <option>$300+</option>
                </select>
            </div>

            <div className={styles.heroInputContainer}>
                <input
                    type="text"
                    placeholder="Aradığın ürünü tarif et..."
                    className={styles.heroInput}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                />
                <button className={styles.heroButton} onClick={handleSend}>
                    <HiPaperAirplane className={styles.sendIcon} />
                </button>
            </div>

            {loading && <div className={styles.loading}>Yükleniyor...</div>}

            <div className={styles.grid}>
                {products.map((product, index) => (
                    <ProductCard
                        key={index}
                        imageUrl={product.image ?? '/placeholder.png'}
                        title={product.title}
                        price={`${product.price.toLocaleString('tr-TR')} TL`}
                        rating={product.rating}
                        reviewCount={product.review_count}
                        description={product.description}
                    />
                ))}
            </div>
        </section>
    );
};

export default ProductRecommender;
