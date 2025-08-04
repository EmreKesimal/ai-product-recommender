import React from "react";
import styles from "./ProductCard.module.css";
import { FaStar } from "react-icons/fa";

interface ProductCardProps {
    imageUrl: string;
    title: string;
    price: string;
    rating: number;
    rating_count: number;
    description: string;
    onClick?: () => void;
}

const renderStars = (rating: number) => {
    const stars = [];
    for (let i = 1; i <= 5; i++) {
        const filledPercentage = Math.min(Math.max(rating - (i - 1), 0), 1) * 100;

        stars.push(
            <div
                key={i}
                style={{
                    width: '14px',
                    height: '14px',
                    position: 'relative',
                }}
            >
                <FaStar
                    size={14}
                    style={{
                        color: '#e5e7eb',
                        position: 'absolute',
                        top: 0,
                        left: 0,
                    }}
                />
                <FaStar
                    size={14}
                    style={{
                        color: 'var(--primary-color)',
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: `${filledPercentage}%`,
                        overflow: 'hidden',
                    }}
                />
            </div>
        );
    }
    return stars;
};


const ProductCard: React.FC<ProductCardProps> = ({
                                                     imageUrl,
                                                     title,
                                                     price,
                                                     rating,
                                                     rating_count,
                                                     description,
                                                     onClick,
                                                 }) => {
    return (
        <div className={styles.card}>
            <img src={imageUrl} alt={title} className={styles.image} />

            <div>
                <h3 className={styles.title}>{title}</h3>

                <div className={styles.rating}>
                    {renderStars(rating)}
                    <span className={styles.reviewText}>
                        ({Number(rating_count).toLocaleString()} değerlendirme)
                    </span>
                </div>



                <p className={styles.price}>{price}</p>
                <button className={styles.shopButton}>Satın Al</button>

                <div className={styles.box}>
                    <p className={styles.paragraph}>{description}</p>
                </div>



            </div>
        </div>

    );
};
export default ProductCard;