"use client";

import { HiPaperAirplane } from "react-icons/hi2";
import styles from "./HeroSection.module.css";

export default function HeroSection() {
    return (
        <section className={styles.heroSection}>
            <h1 className={styles.heroTitle}>Yapay Zekâ ile Sana Uygun Ürünü Bul!</h1>
            <p className={styles.heroSubtitle}>
                Tercihlerine göre sana özel ürün önerileri almak için yapay zekâ asistanımızla sohbet etmeye başla.
            </p>

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
