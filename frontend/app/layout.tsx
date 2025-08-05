import "./globals.css";
import { Plus_Jakarta_Sans } from "next/font/google";

const plusJakarta = Plus_Jakarta_Sans({ subsets: ["latin"], weight: ["400", "600", "700"] });


export const metadata = {
    title: "AkılAI",
    description: "Yapay zeka destekli ürün öneri sistemi",
    icons: {
        icon: "/favicon.ico",
        shortcut: "/favicon.ico",
        apple: "/favicon.ico",
    },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="tr">
        <body className={plusJakarta.className}>
        <div className="app-container">
            {children}
        </div>
        </body>
        </html>
    );
}
