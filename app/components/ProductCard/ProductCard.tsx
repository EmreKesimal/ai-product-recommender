import React from "react";
import styles from "./ProductCard.module.css";
import { FaStar } from "react-icons/fa";

interface ProductCardProps {
    imageUrl: string;
    title: string;
    price: string;
    rating: number;
    reviewCount: number;
    description: string;
    features: string[];
    reviewSummary: string[]; // 🆕 Yeni alan
    onClick?: () => void;
}

const ProductCard: React.FC<ProductCardProps> = ({
                                                     imageUrl,
                                                     title,
                                                     price,
                                                     rating,
                                                     reviewCount,
                                                     description,
                                                     features,
                                                     reviewSummary,
                                                     onClick,
                                                 }) => {
    return (
        <div className={styles.card}>
            <img src={imageUrl} alt={title} className={styles.image} />

            <div className={styles.cardContent}>
                <h3 className={styles.title}>{title}</h3>

                <div className={styles.rating}>
                    {Array.from({ length: 5 }).map((_, i) => (
                        <FaStar
                            key={i}
                            size={14}
                            color={i < rating ? "#facc15" : "#e5e7eb"}
                        />
                    ))}
                    <span className={styles.reviewText}>
        ({Number(reviewCount).toLocaleString()} reviews)
      </span>
                </div>

                <p className={styles.price}>{price}</p>
                <button className={styles.shopButton}>Shop Now</button>
                <p className={styles.description}>{description}</p>

                <div className={styles.box}>
                    <ul className={styles.featureList}>
                        {features.slice(0, 3).map((f, i) => (
                            <li key={i} className={styles.featureItem}>{f}</li>
                        ))}
                    </ul>
                </div>

                <div className={styles.box}>
                    <ul className={styles.reviewSummary}>
                        {reviewSummary.slice(0, 3).map((r, i) => (
                            <li key={i} className={styles.reviewItem}>{r}</li>
                        ))}
                    </ul>
                </div>


            </div>
        </div>

    );
};
export default ProductCard;