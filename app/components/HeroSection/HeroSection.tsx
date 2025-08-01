"use client";

import { HiPaperAirplane } from "react-icons/hi2";
import styles from "./HeroSection.module.css";

export default function HeroSection() {
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
                />
                <button className={styles.heroButton}>
                    <HiPaperAirplane className={styles.sendIcon} />
                </button>
            </div>
        </section>
    );
}
