import HeroSection from "./components/HeroSection/HeroSection";
import ProductList from "@/app/components/ProductList/ProductList";

export default function Home() {
  return (
      <main>
        <HeroSection />
          <ProductList></ProductList>
      </main>
  );
}
