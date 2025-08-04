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
    rating_count: number;
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
                    prompt: query
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
        <section className={`${styles.container} ${products.length > 0 ? styles.shifted : ''}`}>
            <h1 className={styles.heroTitle}>AkılAI ile Sana Uygun Ürünü Bul!</h1>
            <p className={styles.heroSubtitle}>
                Bu akıllı öneri sistemi, ihtiyaçlarını yapay zekâ ile analiz eder, ürünler için yapılmış yorumları inceler ve senin için en uygun ürünleri bulur. Ürün tarifini yazman yeterli!<br />
                Şimdilik sadece teknoloji kategorisinde tavsiyeler verebilmekte.
            </p>

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

            {loading && (
                <div className={styles.loading}>
                    <div>Yükleniyor...</div>
                    <div className={styles.spinner}></div>
                </div>
            )}

            {products.length > 0 && (
                <div className={styles.grid}>
                    {products.map((product, index) => (
                        <ProductCard
                            key={index}
                            imageUrl={product.image ?? '/placeholder.png'}
                            title={product.title}
                            price={`${product.price.toLocaleString('tr-TR')} TL`}
                            rating={product.rating}
                            rating_count={product.rating_count}
                            description={product.description}
                        />
                    ))}
                </div>
            )}
        </section>
    );
};

export default ProductRecommender;
