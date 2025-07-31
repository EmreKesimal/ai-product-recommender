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
        description: "Why we recommend this",
        features: [
            "Very comfortable fit",
            "Long battery life",
            "Noise cancelling",
            "Works with any device"
        ],
        reviewSummary: [
            "Excellent sound quality",
            "Battery lasts over 24h",
            "Very lightweight and comfy"
        ]
    },
    {
        imageUrl: "/indir.png",
        title: "Smart Watch Series 5",
        price: "$399.99",
        rating: 5,
        reviewCount: 2764,
        description: "Why we recommend this",
        features: [
            "Step & heart rate tracking",
            "Water resistant",
            "Long battery life",
            "Minimal design"
        ],
        reviewSummary: [
            "Tracks steps very accurately",
            "Elegant and comfortable",
            "Sleep tracking is helpful"
        ]
    },
    {
        imageUrl: "/indir.png",
        title: "Professional Camera Lens",
        price: "$899.99",
        rating: 4,
        reviewCount: 984,
        description: "Why we recommend this",
        features: [
            "High resolution zoom",
            "Great for portraits",
            "Perfect sharpness",
            "Try now & return"
        ],
        reviewSummary: [
            "Great value for professionals",
            "Sharp focus and depth",
            "Amazing build quality"
        ]
    }
];

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
