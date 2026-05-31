import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)

VARIANT_SUFFIXES = [
    "", "Pro", "Plus", "Elite", "Premium",
    "V2", "Deluxe", "Limited Edition", "Classic", "Essential",
]

PRODUCT_TEMPLATES = {
    "Electronics": [
        "Wireless Bluetooth Headphones",
        "USB-C Fast Charging Cable",
        "Portable Power Bank 10000mAh",
        "4K Ultra HD Webcam",
        "Wireless Charging Pad",
        "Smart Wi-Fi Plug",
        "Bluetooth Portable Speaker",
        "Mechanical Gaming Keyboard",
        "Wireless Ergonomic Mouse",
        "Noise Canceling Earbuds",
        "Adjustable Laptop Stand",
        "27-Inch 4K Monitor",
        "External SSD 1TB",
        "Action Camera 4K",
        "Smart Thermostat",
        "Wireless Router WiFi 6",
        "Portable Bluetooth Receiver",
        "LED Desk Lamp",
        "USB Hub Multiport",
        "Car Dash Camera",
        "Smart Video Doorbell",
        "Electric Toothbrush",
        "Fitness Tracker Watch",
        "Drone with Camera",
        "Tablet Stand Holder",
    ],
    "Clothing": [
        "Classic Fit T-Shirt",
        "Slim Fit Polo Shirt",
        "Skinny Jeans",
        "Casual Chino Pants",
        "Denim Jacket",
        "Hooded Sweatshirt",
        "Crew Neck Sweater",
        "Leather Belt",
        "Formal Dress Shirt",
        "Tailored Blazer",
        "Cotton Casual Shorts",
        "Running Sneakers",
        "Canvas Sneakers",
        "Leather Loafers",
        "Winter Parka",
        "Lightweight Rain Jacket",
        "Swim Trunks",
        "High-Waist Yoga Pants",
        "Sports Bra",
        "Floral Casual Dress",
        "Maxi Skirt",
        "Cashmere Scarf",
        "Knitted Beanie Hat",
        "Aviator Sunglasses",
        "Minimalist Leather Wallet",
    ],
    "Home & Garden": [
        "Decorative Throw Pillow Set",
        "Microfiber Bed Sheet Set",
        "Luxury Bath Towel Set",
        "Scented Soy Candle",
        "Modern Wall Clock",
        "Ceramic Plant Pot",
        "Indoor Herb Garden Kit",
        "Stainless Steel Knife Set",
        "Bamboo Cutting Board Set",
        "Porcelain Coffee Mug Set",
        "Gardening Gloves",
        "Wooden Bird Feeder",
        "Expandable Garden Hose",
        "Patio Chair Cushion Set",
        "Collage Photo Frame Set",
        "Decorative Glass Vase",
        "Non-Slip Area Rug",
        "Woven Storage Basket Set",
    ],
    "Books": [
        "The Art of Data Engineering",
        "Python for Data Analysis",
        "SQL for Analytics Professionals",
        "Cloud Architecture Patterns",
        "Machine Learning Fundamentals",
        "The Data Warehouse Toolkit",
        "Clean Code: A Handbook",
        "System Design Interview Guide",
        "Storytelling with Data",
        "The Phoenix Project",
        "Designing Data-Intensive Applications",
        "The Pragmatic Programmer",
        "Lean Analytics",
        "Trustworthy Online Experiments",
        "Database Internals",
    ],
    "Sports & Outdoors": [
        "Premium Yoga Mat",
        "Resistance Band Set",
        "Adjustable Dumbbell Set",
        "Speed Jump Rope",
        "High-Density Foam Roller",
        "Cast Iron Kettlebell",
        "Insulated Stainless Steel Water Bottle",
        "Hiking Backpack 40L",
        "4-Person Camping Tent",
        "Cold-Weather Sleeping Bag",
        "LED Rechargeable Headlamp",
        "Travel Fishing Rod",
        "Road Bike Helmet",
        "Graphite Tennis Racket",
        "Premium Soccer Ball",
    ],
    "Beauty & Personal Care": [
        "Hydrating Face Moisturizer",
        "Vitamin C Brightening Serum",
        "Moisturizing Lip Balm Set",
        "Nourishing Shampoo & Conditioner",
        "Shea Butter Body Lotion",
        "SPF 50 Sunscreen",
        "Professional Eye Shadow Palette",
        "Volumizing Mascara",
        "Liquid Foundation",
        "Gel Nail Polish Set",
        "Organic Beard Oil",
        "Ultrasonic Essential Oil Diffuser",
        "Ionic Hair Dryer",
    ],
    "Toys & Games": [
        "Creative Building Blocks Set",
        "Strategy Board Game Collection",
        "Remote Control Racing Car",
        "1000-Piece Jigsaw Puzzle",
        "Superhero Action Figure",
        "Plush Teddy Bear",
        "STEM Science Experiment Kit",
        "Card Game Party Pack",
        "Classic Lego Building Set",
        "Coloring Book Mega Set",
    ],
    "Food & Beverages": [
        "Artisan Roast Coffee Beans",
        "Premium Loose Leaf Tea Collection",
        "Belgian Dark Chocolate Bar",
        "Roasted Mixed Nuts Pack",
        "Organic Maple Granola",
        "Artisanal Hot Sauce Set",
        "Extra Virgin Olive Oil",
        "Gourmet Microwave Popcorn",
        "Plant-Based Protein Bars",
        "Raw Manuka Honey Jar",
    ],
}


def _assign_product_id(index: int) -> int:
    return index + 1


def _generate_price(price_range: list[float]) -> float:
    low, high = price_range
    return round(random.uniform(low, high), 2)


def _generate_stock_quantity() -> int:
    return random.randint(10, 500)


def _generate_name(template: str, variant_index: int) -> str:
    suffix = VARIANT_SUFFIXES[variant_index % len(VARIANT_SUFFIXES)]
    if not suffix:
        return template
    return f"{template} — {suffix}"


def generate_products(config: dict) -> list[dict]:
    logger.info("Generating products...")
    seed = config["generation"]["seed"]
    random.seed(seed)

    categories = config["generation"]["categories"]
    now = datetime.now()
    created_at = now.isoformat()

    products: list[dict] = []
    product_index = 0

    for category_name, cat_config in categories.items():
        count = cat_config["count"]
        price_range = cat_config["price_range"]
        templates = PRODUCT_TEMPLATES.get(category_name, [f"{category_name} Item"])

        for i in range(count):
            product_index += 1
            template = templates[i % len(templates)]
            variant_idx = i // len(templates)

            products.append(
                {
                    "product_id": _assign_product_id(product_index - 1),
                    "name": _generate_name(template, variant_idx),
                    "category": category_name,
                    "price": _generate_price(price_range),
                    "stock_quantity": _generate_stock_quantity(),
                    "description": f"{_generate_name(template, variant_idx)} — {category_name}",
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )

    logger.info(
        "Generated %d products across %d categories",
        len(products),
        len(categories),
    )
    return products
