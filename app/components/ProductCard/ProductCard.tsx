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
                    {Array.from({ length: 5 }).map((_, i) => (
                        <FaStar
                            key={i}
                            size={14}
                            color={i < rating ? "var(--primary-color)" : "#e5e7eb"}
                        />
                    ))}
                    <span className={styles.reviewText}>
        ({Number(rating_count).toLocaleString()} ratings)
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